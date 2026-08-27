#!/usr/bin/env python3
"""
Repairs SPEC files from GANS:
  1. Un-merges Epoch/Det_00 fields that glue together once Det_00 reaches
     5 digits.
  2. Drops any bare control line (e.g. "#Q" with no HKL payload on a
     two-circle geometry, no space after the code at all) that crashes
     loaders assuming every "#code data" line has a space after the
     code (e.g. reductus' gansref.py: ValueError: not enough values to
     unpack).

Usage: python3 repair_spec.py input.spec output.spec
       python3 repair_spec.py input.spec > output.spec   (also works)
"""
import re, sys
from datetime import datetime

FMT = "%a %b %d %H:%M:%S %Y"


def candidate_splits(merged):
    parts = merged.split('.', 1)
    int_part = parts[0]
    dec_part = parts[1] if len(parts) > 1 else None
    out = []
    for k in range(1, len(int_part)):
        e_str, d_str = int_part[:k], int_part[k:]
        if e_str.startswith('0') or (d_str.startswith('0') and d_str != '0'):
            continue
        epoch = int(e_str)
        det = d_str + ('.' + dec_part if dec_part else '')
        out.append((epoch, det))
    return out


def is_bare_control_line(line):
    """True for a '#'-line with no space at all after its code (e.g. '#Q\n'),
    the exact shape that breaks 'code, data = line.split("#")[1].split(" ", 1)'
    in reductus' gansref.py. These lines carry no payload anyway (HKL on a
    two-circle geometry), so we drop them rather than patch them."""
    body = line.rstrip('\n')
    if not body.startswith('#'):
        return False
    rest = body[1:]
    return ' ' not in rest


def repair(path):
    with open(path) as f:
        raw_lines = f.readlines()

    out_lines = []
    file_open_dt = None
    labels, n_expected, T, scan_D = None, None, None, None
    epoch_idx = None
    prev_epoch = None

    for line in raw_lines:
        stripped = line.rstrip('\n')
        if stripped.startswith('#D') and file_open_dt is None:
            file_open_dt = datetime.strptime(stripped[3:].strip(), FMT)
        if stripped.startswith('#S'):
            labels = n_expected = T = scan_D = epoch_idx = None
            prev_epoch = None
        elif stripped.startswith('#D') and scan_D is None and file_open_dt is not None:
            scan_D = datetime.strptime(stripped[3:].strip(), FMT)
        elif stripped.startswith('#T'):
            T = float(stripped.split()[1])
        elif stripped.startswith('#N'):
            n_expected = int(stripped.split()[1])
        elif stripped.startswith('#L'):
            labels = re.split(r'\s{2,}', stripped[3:].strip())
            epoch_idx = labels.index('Epoch') if 'Epoch' in labels else None

        is_data = (labels and n_expected and epoch_idx is not None
                   and stripped.strip() and not stripped.startswith('#'))

        if is_data:
            toks = stripped.split()
            if len(toks) == n_expected - 1:
                merged = toks[epoch_idx]
                seed = (scan_D - file_open_dt).total_seconds() if scan_D else 0
                target = (prev_epoch + T) if prev_epoch is not None else (seed + T)
                cands = candidate_splits(merged)
                if cands:
                    epoch, det = min(cands, key=lambda c: abs(c[0] - target))
                    toks = toks[:epoch_idx] + [str(epoch), det] + toks[epoch_idx+1:]
                    prev_epoch = epoch
                out_lines.append(' '.join(toks) + '\n')
                continue
            elif len(toks) == n_expected:
                prev_epoch = int(float(toks[epoch_idx]))
            out_lines.append(line if line.endswith('\n') else line + '\n')
            continue

        if stripped.startswith('#'):
            if is_bare_control_line(line):
                continue  # drop it entirely
            out_lines.append(line if line.endswith('\n') else line + '\n')
        else:
            out_lines.append(line if line.endswith('\n') else line + '\n')

    return out_lines


if __name__ == '__main__':
    lines = repair(sys.argv[1])
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w') as f:
            f.writelines(lines)
    else:
        for l in lines:
            sys.stdout.write(l)