# Copyright Lightning AI. Licensed under the Apache License 2.0, see LICENSE file.

import pytest
import torch

from lit_gpt.datamodules.base import get_sft_collate_fn
from lit_gpt.datamodules.sft_dataset_base import SFTDataset
from lit_gpt.prompts import PromptStyle


@pytest.mark.parametrize('mask_prompt', [True, False])
@pytest.mark.parametrize('ignore_index', [-1, -100])
@pytest.mark.parametrize('max_seq_length', [1000])
def test_sft_dataset(max_seq_length, ignore_index, mask_prompt, MOCK_TOKENIZER_FIXTURE):
    class Style(PromptStyle):
        def apply(self, prompt, **kwargs):
            return f'In: {prompt} Out:'

    i = ignore_index
    data = [
        {'instruction': 'Foo', 'output': 'Bar'},
        {'instruction': 'Boo', 'output': 'Ahh'},
    ]

    dataset = SFTDataset(
        data=data,
        tokenizer=MOCK_TOKENIZER_FIXTURE,
        prompt_style=Style(),
        mask_prompt=mask_prompt,
        ignore_index=ignore_index,
        max_seq_length=max_seq_length,
    )
    assert len(dataset) == len(data)

    expected_input_ids = torch.tensor(
        [1, 73, 110, 58, 32, 70, 111, 111, 32, 79, 117, 116, 58, 66, 97, 114, 2]
    )
    # If prompt is not masked, labels == input_ids
    expected_labels = (
        torch.tensor([i, i, i, i, i, i, i, i, i, i, i, i, i, 66, 97, 114, 2])
        if mask_prompt
        else expected_input_ids
    )

    assert torch.equal(dataset[0]['input_ids'], expected_input_ids[:max_seq_length])
    assert torch.equal(dataset[0]['labels'], expected_labels[:max_seq_length])


@pytest.mark.parametrize('mask_prompt', [True, False])
@pytest.mark.parametrize('ignore_index', [-1, -100])
@pytest.mark.parametrize('max_seq_length', [5])
def test_sft_dataset_hit_max_seq_length(
    max_seq_length, ignore_index, mask_prompt, MOCK_TOKENIZER_FIXTURE
):
    class Style(PromptStyle):
        def apply(self, prompt, **kwargs):
            return f'In: {prompt} Out:'

    i = ignore_index
    data = [
        {'instruction': 'Foo', 'output': 'Bar'},
        {'instruction': 'Boo', 'output': 'Ahh'},
    ]

    dataset = SFTDataset(
        data=data,
        tokenizer=MOCK_TOKENIZER_FIXTURE,
        prompt_style=Style(),
        mask_prompt=mask_prompt,
        ignore_index=ignore_index,
        max_seq_length=max_seq_length,
    )
    assert len(dataset) == len(data)

    eos = torch.tensor([MOCK_TOKENIZER_FIXTURE.eos_id])

    expected_input_ids = torch.tensor(
        [1, 73, 110, 58, 32, 70, 111, 111, 32, 79, 117, 116, 58, 66, 97, 114, 1]
    )
    # If prompt is not masked, labels == input_ids
    expected_labels = (
        torch.tensor([i, i, i, i, i, i, i, i, i, i, i, i, i, 66, 97, 114, 1])
        if mask_prompt
        else expected_input_ids
    )

    assert torch.equal(
        dataset[0]['input_ids'],
        torch.concat((expected_input_ids[: max_seq_length - 1], eos)),
    )

    # If the prompt is not masked, we won't see the eos token
    # Although we should, but this is too trival a problem to fix
    # And it is more likely to occur for training very low context window models,
    # using dataset with high tokens length or without filtering them,
    # i.e, context window 2k, but dataset often has prompts (not even response yet) exceeding that.
    if mask_prompt:
        assert torch.equal(dataset[0]['labels'], expected_labels[:max_seq_length])
    else:
        assert torch.equal(
            dataset[0]['labels'],
            torch.concat((expected_labels[: max_seq_length - 1], eos)),
        )


@pytest.mark.parametrize('ignore_index', [-1, -100])
@pytest.mark.parametrize('pad_id', [0, 100])
def test_sft_collate_fn_padding(pad_id, ignore_index):
    collate = get_sft_collate_fn(pad_id=pad_id, ignore_index=ignore_index)
    samples = [
        {'input_ids': torch.tensor([1, 2, 3]), 'labels': torch.tensor([10, 20, 30])},
        {
            'input_ids': torch.tensor([4, 5, 6, 7, 8]),
            'labels': torch.tensor([40, 50, 60, 70, 80]),
        },
    ]
    expected = {
        'input_ids': torch.tensor([[1, 2, 3, pad_id, pad_id], [4, 5, 6, 7, 8]]),
        'labels': torch.tensor(
            [[10, 20, 30, ignore_index, ignore_index], [40, 50, 60, 70, 80]]
        ),
    }
    batch = collate(samples)
    assert all(torch.equal(batch[k], expected[k]) for k in ('input_ids', 'labels'))


def test_sft_collate_fn_truncation():
    default_eos_token = 2
    collate = get_sft_collate_fn(max_seq_length=2)
    samples = [
        {'input_ids': torch.tensor([1, 2, 3]), 'labels': torch.tensor([10, 20, 30])},
        {
            'input_ids': torch.tensor([4, 5, 6, 7, 8]),
            'labels': torch.tensor([40, 50, 60, 70, 80]),
        },
    ]
    expected = {
        # It should truncate and make sure the last token is the eos token
        'input_ids': torch.tensor([[1, default_eos_token], [4, default_eos_token]]),
        'labels': torch.tensor([[10, default_eos_token], [40, default_eos_token]]),
    }
    batch = collate(samples)
    assert all(torch.equal(batch[k], expected[k]) for k in ('input_ids', 'labels'))
