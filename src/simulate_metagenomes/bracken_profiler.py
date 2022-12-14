#!/usr/bin/env python3
"""
Author : Kenneth Schackart <schackartk1@gmail.com>
Date   : 2022-02-09
Purpose: Create profile from Bracken output
"""

import argparse
import os
import pandas as pd
from pandas.testing import assert_frame_equal
from typing import List, NamedTuple, TextIO, Tuple

from phage_injector import rescale_abundances
from phage_injector import get_phage_content, supplement_phage

pd.options.mode.chained_assignment = None


class Args(NamedTuple):
    """ Command-line arguments """
    profiles: List[TextIO]
    taxonomy: TextIO
    outdir: str
    phage: float
    num_phage: int


# ---------------------------------------------------------------------------
def get_args() -> Args:
    """ Get command-line arguments """

    parser = argparse.ArgumentParser(
        description='Create profile from Bracken output',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    inputs = parser.add_argument_group('Input and Output')
    params = parser.add_argument_group('Phage Injection Parameters')

    inputs.add_argument('profiles',
                        metavar='FILE',
                        help='Bracken output file(s)',
                        type=argparse.FileType('rt'),
                        nargs='+')

    inputs.add_argument('-t',
                        '--taxonomy',
                        metavar='FILE',
                        help='Taxonomy mapping file',
                        type=argparse.FileType('rt'),
                        default='../../data/refseq_info/taxonomy.csv')

    inputs.add_argument('-o',
                        '--outdir',
                        metavar='DIR',
                        help='Output directory',
                        type=str,
                        default='out')

    params.add_argument('-p',
                        '--phage',
                        metavar='PCT',
                        help='Minimum phage content',
                        type=float,
                        default=0.05)

    params.add_argument('-np',
                        '--num_phage',
                        metavar='',
                        help='Maximum number of injected phage species',
                        type=int,
                        default=10)

    args = parser.parse_args()

    # Convert percent to decimal
    if args.phage >= 1:
        args.phage = args.phage / 100

    return Args(args.profiles, args.taxonomy, args.outdir, args.phage,
                args.num_phage)


# ---------------------------------------------------------------------------
def main() -> None:
    """ Do the stuff """

    args = get_args()
    out_dir = args.outdir

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    taxonomy_df = clean_taxonomy(pd.read_csv(args.taxonomy))

    for profile in args.profiles:

        print(f'Making profile for file "{profile.name}"...')

        bracken_df = clean_bracken(pd.read_csv(profile, sep='\t'))

        joined_df = join_dfs(bracken_df, taxonomy_df)

        joined_df['rescaled_abundance'] = rescale_abundances(
            joined_df['fraction_total_reads'])

        if get_phage_content(joined_df) < args.phage:
            joined_df = supplement_phage(joined_df, taxonomy_df, args.phage,
                                         args.num_phage)

        files_df = make_files_df(joined_df)
        profile_df = make_profile_df(joined_df)

        files_output, profile_output = make_filenames(out_dir, profile.name)

        files_df.to_csv(files_output, sep=",", index=False)
        profile_df.to_csv(profile_output, sep="\t", index=False, header=False)

        print('Finished.')

    n_profiles = len(args.profiles)
    plu = 's' if n_profiles != 1 else ''
    print(f'Done. Wrote {n_profiles} profile{plu} to {out_dir}.')


# ---------------------------------------------------------------------------
def clean_bracken(df: pd.DataFrame) -> pd.DataFrame:
    """ Clean bracken output dataframe """

    df = df[df['fraction_total_reads'] > 0.]

    df.drop([
        'name', 'taxonomy_lvl', 'kraken_assigned_reads', 'added_reads',
        'new_est_reads'
    ],
            axis='columns',
            inplace=True)

    df.sort_values('fraction_total_reads',
                   ascending=False,
                   inplace=True,
                   ignore_index=True)

    return df


# ---------------------------------------------------------------------------
def test_clean_bracken() -> None:
    """ Test clean_bracken() """

    in_df = pd.DataFrame([[
        'Maydup orguhnizum', 000000, 'S', 36, 264, 300, 0.0003
    ], ['Methanococcus voltae', 456320, 'S', 365288, 287012, 652300, 0.6523]],
                         columns=[
                             'name', 'taxonomy_id', 'taxonomy_lvl',
                             'kraken_assigned_reads', 'added_reads',
                             'new_est_reads', 'fraction_total_reads'
                         ])

    out_df = pd.DataFrame([[456320, 0.6523], [000000, 0.0003]],
                          columns=['taxonomy_id', 'fraction_total_reads'])

    assert_frame_equal(clean_bracken(in_df), out_df)


# ---------------------------------------------------------------------------
def clean_taxonomy(df: pd.DataFrame) -> pd.DataFrame:
    """ Clean taxonomy dataframe """

    df = df[['kingdom', 'genus', 'species', 'accession', 'taxid']]

    # There may be multiple refseq files (accession #)
    # for a given tax_id. I need tax_id to be unique,
    # so I will drop duplicate tax id's, keeping only the
    # first accession.
    df = df.drop_duplicates('taxid').reset_index(drop=True)

    return df


# ---------------------------------------------------------------------------
def test_clean_taxonomy() -> None:
    """ Test clean_taxonomy() """

    in_df = pd.DataFrame(
        [
            [
                'archaea', 'GCF_000006175.1', 'NC_014222.1', 456320, 2188,
                'Archaea', 'Euryarchaeota', 'Methanococci', 'Methanococcales',
                'Methanococcaceae', 'Methanococcus', 'Methanococcus voltae'
            ],
            [  # Same as above, but different seq_id
                'archaea', 'GCF_000006175.1', 'NC_014223.1', 456320, 2188,
                'Archaea', 'Euryarchaeota', 'Methanococci', 'Methanococcales',
                'Methanococcaceae', 'Methanococcus', 'Methanococcus voltae'
            ],
            [
                'bacteria', 'GCF_003860425.1', 'NZ_CP034193.1', 1613, 1613,
                'Bacteria', 'Firmicutes', 'Bacilli', 'Lactobacillales',
                'Lactobacillaceae', 'Limosilactobacillus',
                'Limosilactobacillus fermentum'
            ]
        ],
        columns=[
            'kingdom', 'accession', 'seq_id', 'taxid', 'species_taxid',
            'superkingdom', 'phylum', 'class', 'order', 'family', 'genus',
            'species'
        ])

    out_df = pd.DataFrame(
        [[
            'archaea', 'Methanococcus', 'Methanococcus voltae',
            'GCF_000006175.1', 456320
        ],
         [
             'bacteria', 'Limosilactobacillus',
             'Limosilactobacillus fermentum', 'GCF_003860425.1', 1613
         ]],
        columns=['kingdom', 'genus', 'species', 'accession', 'taxid'])

    assert_frame_equal(clean_taxonomy(in_df), out_df)


# ---------------------------------------------------------------------------
def join_dfs(bracken: pd.DataFrame,
             tax: pd.DataFrame,
             how: str = 'inner',
             drop_dup: bool = True) -> pd.DataFrame:
    """ Join bracken and taxonomy dfs """

    joined_df = pd.merge(bracken,
                         tax,
                         how=how,
                         left_on='taxonomy_id',
                         right_on='taxid')

    if drop_dup:
        joined_df.drop(['taxonomy_id'], axis='columns', inplace=True)

    return joined_df


# ---------------------------------------------------------------------------
def test_join_dfs() -> None:
    """ Test join_dfs() """

    bracken_df = pd.DataFrame(
        [[456320, 0.6523], [000000, 0.0003]],  # No match
        columns=['taxonomy_id', 'fraction_total_reads'])

    tax_df = pd.DataFrame(
        [
            [
                'archaea', 'Methanococcus', 'Methanococcus voltae',
                'GCF_000006175.1', 456320
            ],
            [  # No match
                'bacteria', 'Limosilactobacillus',
                'Limosilactobacillus fermentum', 'GCF_003860425.1', 1613
            ]
        ],
        columns=['kingdom', 'genus', 'species', 'accession', 'taxid'])

    out_df = pd.DataFrame([[
        0.6523, 'archaea', 'Methanococcus', 'Methanococcus voltae',
        'GCF_000006175.1', 456320
    ]],
                          columns=[
                              'fraction_total_reads', 'kingdom', 'genus',
                              'species', 'accession', 'taxid'
                          ])

    assert_frame_equal(join_dfs(bracken_df, tax_df), out_df)


# ---------------------------------------------------------------------------
def make_files_df(df: pd.DataFrame) -> pd.DataFrame:
    """ Create file names of genomes """

    files_df = df[['kingdom', 'accession']]

    files_df['filename'] = pd.Series(
        map(lambda king, acc: os.path.join(king, acc + '*.fna'),
            files_df['kingdom'], files_df['accession']))

    files_df = files_df[['filename', 'accession']]

    return files_df


# ---------------------------------------------------------------------------
def test_make_files_df() -> None:
    """ Test make_files_df() """

    in_df = pd.DataFrame([[0.6523, 'archaea', 'GCF_000006175.1', 456320, 1.0]],
                         columns=[
                             'fraction_total_reads', 'kingdom', 'accession',
                             'taxid', 'rescaled_abundance'
                         ])

    out_df = pd.DataFrame(
        [['archaea/GCF_000006175.1*.fna', 'GCF_000006175.1']],
        columns=['filename', 'accession'])

    assert_frame_equal(make_files_df(in_df), out_df)


# ---------------------------------------------------------------------------
def make_profile_df(df: pd.DataFrame) -> pd.DataFrame:
    """ Create profile of seq IDs and abundances """

    profile_df = df[['accession', 'rescaled_abundance']]

    profile_df['rescaled_abundance'] = round(profile_df['rescaled_abundance'],
                                             5)

    return profile_df


# ---------------------------------------------------------------------------
def test_make_profile_df() -> None:
    """ Test make_profile_df() """

    in_df = pd.DataFrame(
        [[0.3333333, 'archaea', 'GCF_000006175.1', 456320, 0.3333333]],
        columns=[
            'fraction_total_reads', 'kingdom', 'accession', 'taxid',
            'rescaled_abundance'
        ])

    out_df = pd.DataFrame([['GCF_000006175.1', 0.33333]],
                          columns=['accession', 'rescaled_abundance'])

    assert_frame_equal(make_profile_df(in_df), out_df)


# ---------------------------------------------------------------------------
def make_filenames(out_dir: str, infile: str) -> Tuple[str, str]:
    """ Create names of output files """

    base = os.path.basename(infile)

    root, _ = os.path.splitext(base)

    files_output = os.path.join(out_dir, root + '_files.txt')
    profile_output = os.path.join(out_dir, root + '_profile.txt')

    return files_output, profile_output


# ---------------------------------------------------------------------------
def test_make_filenames() -> None:
    """ Test make_filenames() """
    file_names = ('out/input_1_files.txt', 'out/input_1_profile.txt')
    assert make_filenames('out', 'input_1.txt') == file_names
    assert make_filenames('out', 'tests/input_1.txt') == file_names


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    main()
