from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.config import load_config


def main() -> None:
    cfg = load_config(ROOT / "config.toml")
    voice = cfg.voice

    ffmpeg_cfg = str(voice.ffmpeg_executable)
    ffmpeg_found = (
        str(Path(ffmpeg_cfg).resolve())
        if Path(ffmpeg_cfg).is_file()
        else shutil.which(ffmpeg_cfg)
    )

    model_path = Path(voice.tts_piper_model)
    if not model_path.is_absolute():
        model_path = ROOT / model_path

    try:
        import piper  # noqa: F401
        piper_ok = True
    except Exception as exc:
        piper_ok = False
        piper_error = f"{type(exc).__name__}: {exc}"
    else:
        piper_error = ""

    print("TTS enabled:", voice.tts_enabled)
    print("TTS engine:", voice.tts_engine)
    print("TTS interval:", voice.tts_interval_seconds, "s")
    print("Self-aware override:", voice.tts_selfaware_override_enabled)
    print(
        "Override probability @ rampancy 0.66:",
        round(
            min(
                1.0,
                voice.tts_selfaware_base_probability
                + voice.tts_selfaware_rampancy_gain * 0.66,
            ),
            3,
        ),
    )
    print("FFmpeg:", ffmpeg_found or f"MISSING ({ffmpeg_cfg})")
    print(
        "Piper model:",
        str(model_path),
        "OK" if model_path.is_file() else "MISSING",
    )
    print("piper-tts import:", "OK" if piper_ok else piper_error)

    ready = bool(
        voice.tts_enabled
        and ffmpeg_found
        and (
            voice.tts_engine.lower() != "piper"
            or (piper_ok and model_path.is_file())
        )
    )
    print()
    print("TTS RUNTIME CHECK:", "OK" if ready else "NOT READY")


if __name__ == "__main__":
    main()
