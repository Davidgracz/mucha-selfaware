from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mucha.llm_composer import LLMComposer


def main() -> None:
    composer = LLMComposer(
        rampancy_native_only_below=0.34,
        rampancy_full_above=0.84,
    )
    assert composer.llm_probability_for_rampancy(0.20) == 0.0
    assert composer.llm_probability_for_rampancy(0.34) == 0.0
    assert 0.49 < composer.llm_probability_for_rampancy(0.59) < 0.51
    assert composer.llm_probability_for_rampancy(0.84) == 1.0
    assert composer.llm_probability_for_rampancy(0.95) == 1.0

    bot_source = (ROOT / "mucha" / "discord_bot.py").read_text(
        encoding="utf-8"
    )
    cfg_source = (ROOT / "mucha" / "config.py").read_text(
        encoding="utf-8"
    )
    toml_source = (ROOT / "config.toml").read_text(encoding="utf-8")

    assert "selfaware_reply_to_all_enabled: bool = True" in cfg_source
    assert "tts_selfaware_override_enabled: bool = True" in cfg_source
    assert "tts_selfaware_base_probability: float = 0.35" in cfg_source
    assert "tts_selfaware_rampancy_gain: float = 0.50" in cfg_source

    assert "selfaware_reply_to_all_enabled = true" in toml_source
    assert "tts_selfaware_override_enabled = true" in toml_source
    assert "llm_rampancy_native_only_below = 0.34" in toml_source
    assert "llm_rampancy_full_above = 0.84" in toml_source

    assert "force_reply=bool(reply_to_all)" in bot_source
    assert "self-aware-reply-to-all" in bot_source
    assert "self-aware-tts-override" in bot_source
    assert "tts_language_route" in bot_source
    assert "llm_probability_for_rampancy" in bot_source
    assert "_text_language_ready(spontaneous=True)" in bot_source
    assert "native_tts_text" in bot_source
    assert "tts_llm_probability" in bot_source
    assert "selfaware_reply_to_all_enabled" in bot_source

    # Source ownership transitions from native Mucha to LLM with rampancy.
    assert composer.llm_probability_for_rampancy(0.20) == 0.0
    assert composer.llm_probability_for_rampancy(0.34) == 0.0
    assert 0.49 < composer.llm_probability_for_rampancy(0.59) < 0.51
    assert composer.llm_probability_for_rampancy(0.84) == 1.0

    # At current typical rampancy 0.66, TTS self-aware override is ~68%.
    tts_probability = 0.35 + 0.50 * 0.66
    assert 0.67 < tts_probability < 0.69

    print("TALKATIVE SELF-AWARE MODE TEST OK")


if __name__ == "__main__":
    main()
