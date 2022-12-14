#!/usr/bin/env python3
"""
Author : Kenneth Schackart <schackartk1@gmail.com>
Date   : 2021-05-25
Purpose: Chop a genome into simulated contigs
"""

import argparse
import os
import sys
from typing import Dict, List, NamedTuple, TextIO, Tuple, TypedDict
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from collections import defaultdict


class Args(NamedTuple):
    """ Command-line arguments """
    genome: List[TextIO]
    out_dir: str
    length: int
    overlap: int
    blank: bool


# --------------------------------------------------
class SeqAnnotations(TypedDict):
    """ SeqRecord Annotations """
    parent_id: str
    parent_name: str
    frag_start: int
    frag_end: int
    a_pct: float
    c_pct: float
    g_pct: float
    t_pct: float


# --------------------------------------------------
def get_args() -> Args:
    """ Get command-line arguments """

    parser = argparse.ArgumentParser(
        description='Chop a genome into simulated contigs',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('genome',
                        metavar='FILE',
                        help='Input DNA file(s)',
                        type=argparse.FileType('rt'),
                        nargs='+')

    parser.add_argument('-o',
                        '--out_dir',
                        help='Output directory',
                        metavar='DIR',
                        type=str,
                        default='out')

    parser.add_argument('-l',
                        '--length',
                        help='Segment length (b)',
                        metavar='INT',
                        type=int,
                        default='100')

    parser.add_argument('-v',
                        '--overlap',
                        help='Overlap length (b)',
                        metavar='INT',
                        type=int,
                        default='10')

    parser.add_argument('-b',
                        '--blank',
                        help='Write blank when sequence shorter than -l',
                        action='store_true')

    args = parser.parse_args()

    if args.length <= 0:
        parser.error(f'length "{args.length}" must be greater than 0')

    if args.overlap > args.length:
        parser.error(f'overlap "{args.overlap}"'
                     f' cannot be greater than length "{args.length}"')

    return Args(args.genome, args.out_dir, args.length,
                args.overlap, args.blank)


# --------------------------------------------------
def warn(msg) -> None:
    """ Print a message to STDERR """
    print(msg, file=sys.stderr)


# --------------------------------------------------
def die(msg='Fatal error') -> None:
    """ warn() and exit with error """
    warn(msg)
    sys.exit(1)


# --------------------------------------------------
def main() -> None:
    """ The good stuff """

    args = get_args()
    files = args.genome
    out_dir = args.out_dir
    length = args.length
    overlap = args.overlap
    write_blank = args.blank

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    for fh in files:

        frag_recs = []

        for seq_record in SeqIO.parse(fh, "fasta"):

            seq_len = len(seq_record)
            min_overlap = 2*length - seq_len

            if length > seq_len:
                warn(f'Warning: length "{length}" greater than sequence'
                     f' ({seq_record.id}) length ({seq_len}). Skipping.')
                continue
            if overlap < min_overlap:
                warn(f'Warning: overlap "{overlap}" less than minimum'
                     f'overlap: {min_overlap}\n\tminimum '
                     f'overlap =  2 * length - seq_len '
                     f'(2*{length}-{seq_len}={min_overlap}). Skipping.')
                continue

            for frags in chop(seq_record, length, overlap):
                frag_recs.append(frags)

        out_file_base = os.path.splitext(os.path.basename(fh.name))[0]
        out_file_fa = os.path.join(out_dir,  out_file_base + '_frags.fasta')
        out_file_tsv = os.path.join(out_dir,  out_file_base + '_frags.tsv')

        if len(frag_recs) > 0:
            n_rec = SeqIO.write(frag_recs, out_file_fa, "fasta")
            print(f'Wrote {n_rec} records to "{out_file_fa}".')

        if len(frag_recs) == 0:
            if write_blank:
                with open(out_file_fa, 'wt') as out_fh:
                    print('', file=out_fh)
                print(f'Wrote 0 records to "{out_file_fa}".')

        write_annotations(frag_recs, out_file_tsv, write_blank)

    print(f'Done. Processed {len(files)} '
          f'file{"s" if len(files)!= 1 else ""}.')


# --------------------------------------------------
def chop(record: SeqRecord, frag_len: int, overlap: int) -> List[SeqRecord]:
    """ Chop sequence from record """

    starts, stops = get_positions(len(record.seq), frag_len, overlap)

    frag_recs = []
    n_frag = 0

    for start, stop in zip(starts, stops):
        n_frag += 1
        frag = record.seq[start: stop+1]

        freqs = find_tetra(frag)

        frag_annotations = SeqAnnotations(parent_id=record.id,
                                          parent_name=record.description,
                                          frag_start=start + 1,
                                          frag_end=stop + 1,
                                          a_pct=freqs['A'],
                                          c_pct=freqs['C'],
                                          g_pct=freqs['G'],
                                          t_pct=freqs['T']
                                          )

        frag_rec = SeqRecord(frag, id=f'frag_{n_frag}_{record.id}',
                             description=f'Fragment {n_frag}'
                                         f' of {record. description}',
                                         annotations=frag_annotations
                             )

        frag_recs.append(frag_rec)

    return frag_recs


# --------------------------------------------------
def get_positions(length: int, frag: int, overlap: int) -> Tuple:
    """ Get starting and stopping positions """

    starts = [0]
    stops = [frag-1]

    stop = stops[-1]
    while stop < length - 1:
        start = starts[-1] + frag - overlap
        stop = start + frag - 1

        if stop <= length - 1:
            starts.append(start)
            stops.append(stop)

    return (starts, stops)


# --------------------------------------------------
def test_get_positions():
    """ Test get_positions """

    assert get_positions(4, 2, 1) == ([0, 1, 2], [1, 2, 3])
    assert get_positions(4, 2, 0) == ([0, 2], [1, 3])
    assert get_positions(4, 3, 2) == ([0, 1], [2, 3])
    assert get_positions(5, 4, 3) == ([0, 1], [3, 4])
    assert get_positions(5, 3, 2) == ([0, 1, 2], [2, 3, 4])
    assert get_positions(5, 3, 1) == ([0, 2], [2, 4])
    assert get_positions(5, 2, 1) == ([0, 1, 2, 3], [1, 2, 3, 4])
    assert get_positions(5, 2, 0) == ([0, 2], [1, 3])


# --------------------------------------------------
def find_tetra(seq: str) -> Dict[str, float]:
    """ Calculate Tetranucleotide Frequency """

    counts: Dict[str, int] = defaultdict(int)
    freqs: Dict[str, float] = defaultdict(float)

    for base in seq:
        counts[base.upper()] += 1

    for base, count in counts.items():
        freqs[base] = count / len(seq)

    return freqs


# --------------------------------------------------
def test_find_tetra():
    """ Test find_tetra """

    assert find_tetra('') == {}
    assert find_tetra('A') == {'A': 1}
    assert find_tetra('C') == {'C': 1}
    assert find_tetra('G') == {'G': 1}
    assert find_tetra('T') == {'T': 1}
    assert find_tetra('ACCGGGTTTT') == {'A': 0.1, 'C': 0.2, 'G': 0.3, 'T': 0.4}


# --------------------------------------------------
def write_annotations(frag_recs, out_file, write_blank):
    """ Write fragment annotations to .tsv """

    if len(frag_recs) != 0:

        with open(out_file, 'wt') as out_fh:
            print('id', 'name', *frag_recs[0].annotations.keys(),
                  sep='\t', file=out_fh)

            for rec in frag_recs:
                print(rec.id, rec.description, *rec.annotations.values(),
                      sep='\t', file=out_fh)

    elif len(frag_recs) == 0 and write_blank:

        with open(out_file, 'wt') as out_fh:
            print('', file=out_fh)


# --------------------------------------------------
if __name__ == '__main__':
    main()
