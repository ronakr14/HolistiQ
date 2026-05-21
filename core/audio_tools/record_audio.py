import csv
from pathlib import Path

import librosa
import numpy as np
import sounddevice as sd
import soundfile as sf
from core.infrastructure. import prompts
from core.utils.directory_utils import ensure_dir


def check_quality(audio, sample_rate):
    """
    Checks the quality of an audio recording.

    Parameters:
        audio (numpy.ndarray): The audio data to check.
        sample_rate (int): The sample rate of the audio data.

    Returns:
        tuple: A tuple containing a boolean indicating whether the audio meets quality standards, and a string describing the reason if it does not.
    """
    rms = np.sqrt(np.mean(audio**2))
    peak = np.max(np.abs(audio))
    duration = len(audio) / sample_rate

    # Checks
    if duration < 1.5:
        return False, "Too short (maybe silence?)"
    if peak > 0.98:
        return False, "Clipping detected (too loud)"
    if rms < 0.01:
        return False, "Too quiet"
    return True, "Good"


def trim_silence(audio, top_db: int = 25):
    """
    Trims silence from an audio recording.

    Parameters:
        audio (numpy.ndarray): The audio data to trim.
        top_db (int, optional): The threshold in decibels for trimming silence. Defaults to 25.

    Returns:
        numpy.ndarray: The trimmed audio data.
    """
    trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
    return trimmed


def record_audio(
    user: str,
    op_dir: str,
    sample_rate: int = 22050,
    channels: int = 1,
    record_seconds: int = 6,
):
    """
    Records audio from user and saves the recordings to a directory.

    Parameters:
        user (str): The username of the user recording audio.
        op_dir (str, optional): The directory to save the recordings to. Defaults to '.wavs'.
        sample_rate (int, optional): The sample rate of the audio recordings. Defaults to 22050.
        channels (int, optional): The number of channels in the audio recordings. Defaults to 1.
        record_seconds (int, optional): The number of seconds to record audio for. Defaults to 6.

    Returns:
        None
    """
    op_dir = Path(op_dir).resolve()
    ensure_dir(op_dir)
    metadata_file = op_dir / user / "metadata.csv"

    with open(metadata_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter="|")
        for i, prompt in enumerate(prompts):
            while True:
                filename = f"utt_{i:03d}.wav"
                file_path = op_dir / filename
                print(f"Please read the following sentence aloud:\n{prompt}")
                input("Press Enter when ready to start recording...")
                recording = sd.rec(
                    int(record_seconds * sample_rate),
                    samplerate=sample_rate,
                    channels=channels,
                    dtype="float32",
                )

                sd.wait()
                audio = recording.squeeze()
                audio = trim_silence(audio=audio)
                print("Playing back your recording...")
                sd.play(recording, samplerate=sample_rate)
                sd.wait()
                ok, message = check_quality(recording, sample_rate)
                print(f"Quality check: {message}")
                choice = input("Keep this recording? (y/n) ").strip().lower()
                if choice == "y" and ok:
                    sf.write(file_path, recording, sample_rate)
                    writer.writerow([file_path, prompt])
                    print(f"Saved {file_path}\n")
                    break
                else:
                    print("Discarded. Let's try again.")
