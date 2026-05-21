import logging
import os
from datetime import datetime
from multiprocessing import Process, current_process
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd
from performance_data.data_info import DataGenerationConfig
from performance_data.datatype_generator import DataTypeGenerator
from performance_data.file_handler import FileHandler

log = logging.getLogger(__name__)


class Performance:
    """Main class for performance data generation."""

    def __init__(self, env: dict):
        self.config = self._parse_configuration(env)
        self.data_generator = DataTypeGenerator(self.config.distribution)
        self.filename = self._generate_filename()
        self._return_args = {}

        self._validate_configuration()
        self._standardize_datatype_dict()

        self.generate_data()
        self._convert_to_target_format()

    def _parse_configuration(self, env: dict) -> DataGenerationConfig:
        """Parse environment configuration into config object."""
        params = getattr(env, "performance", None)

        config_dict = {
            "columns": int(getattr(params, "columns", 1)) if params else 1,
            "rows": int(getattr(params, "rows", 1)) if params else 1,
            "distribution": (
                getattr(params, "distribution", "uniform") if params else "uniform"
            ),
            "file_format": getattr(params, "file_format", "csv") if params else "csv",
            "destination_folder": (
                getattr(params, "destination_folder", os.getcwd())
                if params
                else os.getcwd()
            ),
            "chunk_size": getattr(params, "batch_size", 10000) if params else 10000,
        }

        # Parse datatype dictionary
        if params and hasattr(params, "datatype_dict"):
            config_dict["datatype_dict"] = self._parse_datatype_dict(
                params.datatype_dict
            )

        return DataGenerationConfig(**config_dict)

    def _parse_datatype_dict(self, datatype_string: str) -> dict[str, int]:
        """Parse datatype dictionary from string format."""
        datatype_dict = {}
        items = datatype_string.replace(" ", "").replace(",", ";").split(";")

        for item in items:
            if ":" in item:
                dtype, cnt = item.split(":")
                datatype_dict[dtype] = datatype_dict.get(dtype, 0) + int(cnt)

        return datatype_dict if datatype_dict else {"int4": 0}

    def _validate_configuration(self) -> None:
        """Validate configuration parameters."""
        total_datatype_columns = sum(self.config.datatype_dict.values())
        if total_datatype_columns > self.config.columns:
            raise ValueError(
                f"Mismatch: total datatype columns ({total_datatype_columns}) "
                f"exceeds specified columns ({self.config.columns})"
            )

    def _standardize_datatype_dict(self) -> None:
        """Standardize datatype dictionary to match column count."""
        total_columns = sum(self.config.datatype_dict.values())
        if total_columns < self.config.columns:
            additional_columns = self.config.columns - total_columns
            self.config.datatype_dict["int4"] += additional_columns

        log.info(f"Standardized datatypes: {self.config.datatype_dict}")

    def _generate_filename(self) -> str:
        """Generate filename based on configuration."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"{self.config.columns}_{self.config.rows}_{self.config.distribution}_{timestamp}"

    def generate_data(self) -> None:
        """Generate data using multiprocessing."""
        with TemporaryDirectory() as temp_dir:
            log.info(f"Created temporary directory: {temp_dir}")

            processes = self._create_processes(temp_dir)
            self._execute_processes(processes)

            csv_path = os.path.join(
                self.config.destination_folder, f"{self.filename}.csv"
            )
            FileHandler.merge_csv_files(temp_dir, csv_path)

    def _create_processes(self, temp_dir: str) -> list[Process]:
        """Create worker processes for data generation."""
        processes = []
        num_processes = (
            self.config.rows + self.config.chunk_size - 1
        ) // self.config.chunk_size

        for i in range(num_processes):
            rows_for_process = self._calculate_rows_for_process(i, num_processes)
            process = Process(
                target=self._write_temp_file, args=(temp_dir, i, rows_for_process)
            )
            processes.append(process)

        return processes

    def _calculate_rows_for_process(
        self, process_index: int, total_processes: int
    ) -> int:
        """Calculate number of rows for a specific process."""
        if process_index == total_processes - 1:
            return self.config.rows - (process_index * self.config.chunk_size)
        return min(self.config.chunk_size, self.config.rows)

    def _execute_processes(self, processes: list[Process]) -> None:
        """Execute all processes and wait for completion."""
        for process in processes:
            process.start()

        for process in processes:
            process.join()

    def _write_temp_file(self, directory: str, chunk_id: int, rows: int) -> None:
        """Write temporary file with generated data."""
        file_path = os.path.join(directory, f"temp_file_{chunk_id}.csv")
        chunk_data = self._generate_chunk_data(rows)

        df = pd.DataFrame(chunk_data)
        df.to_csv(file_path, index=False)

        log.info(f"{current_process().name} wrote {file_path}")

    def _generate_chunk_data(self, rows: int) -> dict[str, Any]:
        """Generate data chunk based on datatype configuration."""
        chunk_data = {}

        for dtype, count in self.config.datatype_dict.items():
            for i in range(count):
                column_name = f"{dtype}_{i + 1}"
                chunk_data[column_name] = self._generate_column_data(dtype, rows)

        return chunk_data

    def _generate_column_data(self, dtype: str, rows: int) -> Any:
        """Generate data for a specific column type."""
        if dtype == "int2":
            return self.data_generator.generate_int2(rows)
        elif dtype == "int4":
            return self.data_generator.generate_int4(rows)
        elif dtype == "int8":
            return self.data_generator.generate_int8(rows)
        elif dtype == "float4":
            return self.data_generator.generate_float4(rows)
        elif dtype == "float8":
            return self.data_generator.generate_float8(rows)
        elif dtype in ["char", "varchar(1)"]:
            return self.data_generator.generate_char(rows)
        elif "varchar" in dtype:
            length = self._extract_varchar_length(dtype)
            return self.data_generator.generate_varchar(rows, length)
        elif dtype == "uuid":
            return self.data_generator.generate_uuid(rows)
        elif dtype == "date":
            return self.data_generator.generate_date(rows)
        elif dtype == "datetime":
            return self.data_generator.generate_datetime(rows)
        elif dtype == "time":
            return self.data_generator.generate_time(rows)
        else:
            log.warning(f"Unknown datatype {dtype}, defaulting to int4")
            return self.data_generator.generate_int4(rows)

    def _extract_varchar_length(self, dtype: str) -> int:
        """Extract length from varchar type specification."""
        if "(" in dtype and ")" in dtype:
            return int(dtype.split("(")[1].replace(")", ""))
        return 64000  # Default for unspecified varchar

    def _convert_to_target_format(self) -> None:
        """Convert generated CSV to target format."""
        csv_path = os.path.join(self.config.destination_folder, f"{self.filename}.csv")
        output_path = FileHandler.convert_to_format(
            csv_path, self.config.file_format, self.config.destination_folder
        )
        self._return_args["filename"] = output_path
