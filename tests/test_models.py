import pytest

from app.schemas.step_config import (
    ActionAddTag,
    ActionGotoStep,
    ActionPayProduct,
    ActionUrl,
    Button,
    ButtonGroup,
    StepConfig,
    TextMessage,
)


def test_empty_step_config():
    config = StepConfig()
    assert config.delay_before_seconds == 0
    assert config.wait_for_payment is False
    assert config.blocks == []
    assert config.next_step == "auto"


def test_step_with_text_and_buttons():
    config = StepConfig(
        blocks=[
            TextMessage(type="text", content="Hello"),
            ButtonGroup(
                type="buttons",
                buttons=[
                    Button(text="URL", action=ActionUrl(type="url", value="https://t.me")),
                    Button(text="Goto", action=ActionGotoStep(type="goto_step", value="next_step")),
                    Button(text="Tag", action=ActionAddTag(type="add_tag", value="clicked")),
                    Button(text="Pay", action=ActionPayProduct(type="pay_product", value="community")),
                ],
            ),
        ]
    )
    assert len(config.blocks) == 2
    assert config.blocks[1].buttons[0].action.type == "url"


def test_serialization_roundtrip():
    config = StepConfig(
        blocks=[TextMessage(type="text", content="Test")],
        add_tags_after=["test_tag"],
    )
    data = config.model_dump(mode="json")
    restored = StepConfig(**data)
    assert restored.blocks[0].content == "Test"
    assert restored.add_tags_after == ["test_tag"]


def test_invalid_action_type_rejected():
    with pytest.raises(Exception):
        StepConfig(
            blocks=[
                ButtonGroup(
                    type="buttons",
                    buttons=[
                        {"text": "Bad", "action": {"type": "unknown", "value": "x"}},
                    ],
                ),
            ]
        )