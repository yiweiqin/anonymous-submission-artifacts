"""Exercise padded decoder output slicing without allocating model weights."""
import contextlib
import sys
import types
import unittest
from unittest.mock import patch

from evaluate import generate_batches


class Inputs(dict):
    def to(self, device):
        return self


class Tokenizer:
    pad_token_id = 0

    def apply_chat_template(self, messages, **kwargs):
        return messages[0]['content']

    def __call__(self, texts, **kwargs):
        assert kwargs == {'return_tensors': 'pt', 'padding': True, 'add_special_tokens': False}
        width = max(map(len, texts))
        return Inputs(input_ids=types.SimpleNamespace(shape=(len(texts), width)),
                      attention_mask='mask', lengths=list(map(len, texts)))

    def decode(self, tokens, **kwargs):
        return ','.join(map(str, tokens))


class Model:
    device = 'cpu'

    def generate(self, input_ids, lengths, attention_mask, **kwargs):
        assert attention_mask == 'mask'
        assert kwargs['do_sample'] is False
        # Prefix contains both padded and real prompt positions. Only suffixes
        # should survive decoding, including in the final short batch.
        return [[0] * input_ids.shape[1] + [length, 99] for length in lengths]


class BatchTests(unittest.TestCase):
    def test_left_padding_suffix_order_and_short_last_batch(self):
        tok = Tokenizer()
        with patch.dict(sys.modules, torch=types.SimpleNamespace(inference_mode=contextlib.nullcontext)), \
             patch('evaluate.prompt', side_effect=lambda c: c):
            generated = generate_batches(['ab', 'abcde', 'z'], Model(), tok,
                                         {'maxLength': 20, 'maxNewTokens': 4}, 2)
            result = list(generated)
        self.assertEqual([r[0] for r in result], ['2,99', '5,99', '1,99'])
        self.assertEqual(tok.padding_side, 'left')
        self.assertTrue(all(seconds >= 0 for _, seconds in result))

    def test_context_overflow_does_not_truncate(self):
        with patch.dict(sys.modules, torch=types.SimpleNamespace(inference_mode=contextlib.nullcontext)), \
             patch('evaluate.prompt', side_effect=lambda c: c):
            with self.assertRaisesRegex(ValueError, 'inference_budget_overflow'):
                list(generate_batches(['abcdef'], Model(), Tokenizer(),
                                      {'maxLength': 8, 'maxNewTokens': 4}, 2))


if __name__ == '__main__':
    unittest.main()
