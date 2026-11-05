"""Precision/recall of the identity matcher on a hand-labelled pair set (tests/fixtures/identity_pairs.json).

The pairs were written by the maintainers to cover easy positives, hard negatives and positives we
accept missing. Treat the numbers as a regression guard, not as accuracy on real-world data.
"""
import json
from pathlib import Path

from app.quality.identity import same_person

PAIRS = json.loads((Path(__file__).parent / 'fixtures' / 'identity_pairs.json').read_text())


def evaluate():
    tp = fp = fn = tn = 0
    wrong = []
    for p in PAIRS:
        pred = same_person(p['a'], p['b'])
        if pred and p['same']:
            tp += 1
        elif pred and not p['same']:
            fp += 1
            wrong.append(('FALSE MERGE', p['note']))
        elif not pred and p['same']:
            fn += 1
            wrong.append(('missed', p['note']))
        else:
            tn += 1
    return tp, fp, fn, tn, wrong


def test_no_false_merges():
    # Merging two strangers corrupts data, so precision must be perfect on this set.
    tp, fp, fn, tn, wrong = evaluate()
    assert fp == 0, [w for w in wrong if w[0] == 'FALSE MERGE']


def test_recall_floor_and_known_misses():
    tp, fp, fn, tn, wrong = evaluate()
    recall = tp / (tp + fn)
    assert recall >= 0.8, (recall, wrong)
    missed = {note for kind, note in wrong if kind == 'missed'}
    assert missed <= {'only the name matches (not enough evidence by design)',
                      'nothing machine-checkable in common'}


def test_dataset_is_balanced_enough_to_mean_something():
    positives = sum(p['same'] for p in PAIRS)
    assert positives >= 10 and len(PAIRS) - positives >= 10
