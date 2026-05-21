import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Union

import psutil

from libs.mixers.logger_mixin import get_logger

logger = get_logger("Sys", component="Utils")


# Hardware detection patterns
_CLOUD_PATTERNS = {
    "google": ["google.colab", "google.cloud"],
    "azure": ["azureml", "azure"],
    "aws": ["sagemaker", "boto3", "awscli"],
    "databricks": ["databricks", "pyspark"],
    "kaggle": ["kaggle"],
    "paperspace": ["gradient"],
}

# Environment variable type conversion
_TYPE_CONVERTERS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": lambda x: x.lower() in ("true", "1", "yes", "on"),
    "list": lambda x: [item.strip() for item in x.split(",") if item.strip()],
    "path": Path,
}


@lru_cache(maxsize=1)
def get_hardware_type() -> str:
    """
    Detect the current hardware/cloud environment.

    Returns:
        String identifier for the detected environment
    """
    logger.debug("Detecting hardware environment")

    # Check for cloud environments
    for cloud, patterns in _CLOUD_PATTERNS.items():
        if any(pattern in sys.modules for pattern in patterns):
            logger.info(f"Detected {cloud} environment")
            return cloud

    # Check for GPU availability
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"Local environment with GPU: {gpu_name}")
            return f"local_gpu_{torch.cuda.device_count()}"
    except ImportError:
        pass

        # Check for common HPC indicators
        if any(env in os.environ for env in ["SLURM_JOB_ID", "PBS_JOBID", "LSB_JOBID"]):
            return "hpc_cluster"

        return "local"


@lru_cache(maxsize=1)
def get_system_info(cls) -> dict[str, Any]:
    """Get comprehensive system information."""
    logger.debug("Gathering system information")

    try:
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        info = {
            # Basic system info
            "platform": platform.platform(),
            "system": platform.system(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "architecture": platform.architecture(),
            "python_version": platform.python_version(),
            "hostname": socket.gethostname(),
            # Hardware info
            "cpu_count": psutil.cpu_count(),
            "cpu_count_logical": psutil.cpu_count(logical=True),
            "memory_total_gb": round(memory.total / (1024**3), 2),
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_free_gb": round(disk.free / (1024**3), 2),
            # Environment info
            "hardware_type": cls.get_hardware_type(),
            "working_directory": str(Path.cwd()),
            "temp_directory": tempfile.gettempdir(),
            "user": os.getenv("USER", os.getenv("USERNAME", "unknown")),
        }

        # Add GPU info if available
        try:
            import torch

            if torch.cuda.is_available():
                info.update(
                    {
                        "gpu_available": True,
                        "gpu_count": torch.cuda.device_count(),
                        "gpu_names": [
                            torch.cuda.get_device_name(i)
                            for i in range(torch.cuda.device_count())
                        ],
                        "cuda_version": torch.version.cuda,
                    }
                )
        except ImportError:
            info["gpu_available"] = False

        return info

    except Exception as e:
        logger.warning(f"Error gathering system info: {e}")
        return {"error": str(e)}


def check_dependencies(
    packages: list[str], install_missing: bool = False
) -> dict[str, bool]:
    """
    Check if required packages are installed.

    Args:
        packages: List of package names to check
        install_missing: Whether to attempt pip install for missing packages

    Returns:
        Dict mapping package names to availability status
    """
    results = {}
    missing = []

    for package in packages:
        try:
            __import__(package)
            results[package] = True
            logger.debug(f"Package '{package}' is available")
        except ImportError:
            results[package] = False
            missing.append(package)
            logger.warning(f"Package '{package}' is missing")

    if install_missing and missing:
        logger.info(f"Attempting to install missing packages: {missing}")
        for package in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                results[package] = True
                logger.info(f"Successfully installed '{package}'")
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to install '{package}': {e}")

    return results


def get_available_port(start_port: int = 8000, max_attempts: int = 100) -> int:
    """
    Find an available port starting from start_port.

    Args:
        start_port: Port to start checking from
        max_attempts: Maximum number of ports to check

    Returns:
        Available port number
    """
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                logger.debug(f"Found available port: {port}")
                return port
        except OSError:
            continue

    raise RuntimeError(
        f"No available port found in range {start_port}-{start_port + max_attempts}"
    )


def get_disk_usage(path: Union[str, Path] = ".") -> dict[str, float]:
    """
    Get disk usage information for a path.

    Args:
        path: Path to check disk usage for

    Returns:
        Dict with total, used, free space in GB
    """
    try:
        usage = shutil.disk_usage(path)
        return {
            "total_gb": round(usage.total / (1024**3), 2),
            "used_gb": round((usage.total - usage.free) / (1024**3), 2),
            "free_gb": round(usage.free / (1024**3), 2),
            "usage_percent": round(((usage.total - usage.free) / usage.total) * 100, 2),
        }
    except Exception as e:
        logger.error(f"Failed to get disk usage for {path}: {e}")
        raise


def monitor_process(
    pid: int, interval: float = 1.0, duration: float = 10.0
) -> dict[str, list[float]]:
    """
    Monitor process resource usage.

    Args:
        pid: Process ID to monitor
        interval: Monitoring interval in seconds
        duration: Total monitoring duration in seconds

    Returns:
        Dict with lists of CPU and memory usage over time
    """
    try:
        process = psutil.Process(pid)
        cpu_usage = []
        memory_usage = []
        timestamps = []

        start_time = time.time()
        while (time.time() - start_time) < duration:
            try:
                cpu_percent = process.cpu_percent()
                memory_mb = process.memory_info().rss / (1024 * 1024)

                cpu_usage.append(cpu_percent)
                memory_usage.append(memory_mb)
                timestamps.append(time.time() - start_time)

                time.sleep(interval)
            except psutil.NoSuchProcess:
                logger.warning(f"Process {pid} terminated during monitoring")
                break

        return {
            "timestamps": timestamps,
            "cpu_percent": cpu_usage,
            "memory_mb": memory_usage,
            "avg_cpu": sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0,
            "avg_memory_mb": (
                sum(memory_usage) / len(memory_usage) if memory_usage else 0
            ),
        }

    except psutil.NoSuchProcess:
        logger.error(f"Process {pid} not found")
        raise ValueError(f"Process {pid} not found")


def cleanup_temp_files(pattern: str = "holistiq_*", older_than_hours: int = 24) -> int:
    """
    Clean up temporary files matching a pattern.

    Args:
        pattern: Glob pattern for files to clean
        older_than_hours: Only delete files older than this many hours

    Returns:
        Number of files deleted
    """
    temp_dir = Path(tempfile.gettempdir())
    cutoff_time = time.time() - (older_than_hours * 3600)
    deleted_count = 0

    try:
        for file_path in temp_dir.glob(pattern):
            if file_path.stat().st_mtime < cutoff_time:
                file_path.unlink()
                deleted_count += 1
                logger.debug(f"Deleted temp file: {file_path}")

        logger.info(f"Cleaned up {deleted_count} temporary files")
        return deleted_count

    except Exception as e:
        logger.error(f"Error cleaning temp files: {e}")
        return deleted_count
