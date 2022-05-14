#! /usr/bin/env python3

import csv
from argparse import ArgumentParser, ArgumentTypeError, FileType
import matplotlib.pyplot as plt
import numpy as np
import os.path
import sys


def ordinal_suffix(number):
    '''
    get the suffix for a ordinal numeral in english ('st' for 1, 'nd' for 2 etc.)
    '''
    last_digit = number % 10
    if last_digit == 1:
        return 'st'
    elif last_digit == 2:
        return 'nd'
    elif last_digit == 3:
        return 'rd'
    else:
        return 'th'


def gen_plot_points(tsv_file, markersize, show, verbose):
    '''
    generate a point plot from a .tsv file

    parameters:
        - tsv_file: opened .tsv file containing the data that will be plotted
        - markersize: float determining the size of the plotted points
        - show: boolean that determines whether the plot will be shown (if show == True) or written to a file
        - verbose: boolean that determines whether information is written to stdout
    '''
    if verbose and not show:
        print(f'Plotting {tsv_file.name}... ', end='')

    arrival_times = csv.reader(tsv_file, delimiter='\t')
    # numpy needs something array-like, thus the conversion to a list
    # also we only need the second column of every entry
    deltas = np.array(list(arrival_times), dtype=float)[:, 1]

    plt.plot(np.arange(len(deltas)), deltas, '.', markersize=markersize)
    plt.xlabel('Packet number')
    plt.ylabel('Delta delay')
    plt.title('Consecutive packet delay difference')

    if show:
        plt.show()
    else:
        extension_index = tsv_file.name.rfind(".")
        extension_index = len(tsv_file.name) if extension_index == -1 else extension_index
        plt.savefig(f'{tsv_file.name[:extension_index]}.pdf', format='pdf', bbox_inches='tight')

    if verbose and not show:
        print('done.')


def gen_plot_distribution(tsv_files_with_names, bin_size, percentile, limits, clip, show, verbose):
    '''
    generate a distribution plot from multiple .tsv files

    parameters:
        - tsv_files_with_names: list of tuples, each containing an opened .tsv file and the legend label for that data set
        - bin_size: bin size for generating the distribution histograms
        - percentile: what percentile of the data to use, see argparse help for more. ignored if limits is not None
        - limits: tuple of floats determining what part of the data to be used, see argparse help for more. must be None if percentile should be used
        - clip: boolean that determines whether data outside the range determined by percentile/limits will be clipped to the smallest/biggest allowed value
        - show: boolean that determines whether the plot will be shown (if show == True) or written to a file
        - verbose: boolean that determines whether information is written to stdout
    '''
    width = bin_size / (len(tsv_files_with_names) + 0)  # TODO: 1 or bin_size as numerator?
    deltas = [None for _ in range(len(tsv_files_with_names))]

    for i, (file, _) in enumerate(tsv_files_with_names):
        if verbose:
            print(f'Generating distribution for {file.name}... ', end='')
            sys.stdout.flush()

        arrival_times = csv.reader(file, delimiter='\t')
        # numpy needs something array-like, thus the conversion to a list
        # also we only need the second column of every entry
        deltas[i] = np.array(list(arrival_times), dtype=float)[:, 1]

    if limits is None:
        bin_min = min(np.percentile(d, 100 - percentile) for d in deltas)
        bin_max = max(np.percentile(d, percentile) for d in deltas)
    else:
        bin_min, bin_max = limits
    
    if clip:
        for i in range(len(deltas)):
            deltas[i] = np.clip(deltas[i], bin_min, bin_max)

    # we need to add bin_size twice to the upper limit because
    # 1. we want the last bin to be [bin_max, bin_max + bin_size] and not [bin_max - bin_size, bin_max] for symmetry reasons
    # 2. np.arange excludes the upper limit but we want it to be included (adding any value larger than zero and less or equal to the step size,
    #    i. e. bin_size, would work)
    bins = np.arange(bin_min, bin_max + 2*bin_size, bin_size)
    fig, ax = plt.subplots()

    for i, d in enumerate(deltas):
        histo, bin_edges = np.histogram(d, bins=bins)
        histo = histo / np.sum(histo)  # calculate ratio, use np.sum(histo) instead of len(deltas) because we may have discarded some values
        ax.bar(bin_edges[:-1] + width*i, histo, width, label=tsv_files_with_names[i][1])

    if verbose:
        print('done.')
    
    if clip:
        # remove major ticks that would collide with the minor ticks for bin_min and bin_max
        xticks = [t for t in ax.get_xticks() if (t != float(int(bin_min))) and (t != float(int(bin_max)))]
        xticks = xticks[1:-1]  # don't include outmost ticks
        xlabels = [str(int(t)) for t in xticks]
        ax.set_xticks(xticks)
        ax.set_xticklabels(xlabels)

        # add minor ticks for bin_min and bin_max
        ax.set_xticks([float(int(bin_min)), float(int(bin_max))], minor=True)
        ax.set_xticklabels([f'$\\leq${int(bin_min)}', f'$\\geq${int(bin_max)}'], minor=True, rotation=45)

    ax.set_xlabel('Delay differences [ms]')
    ax.set_ylabel('Ratio')
    ax.set_title('Distribution of consecutive packet delay difference')
    ax.legend(loc='upper right')

    if show:
        plt.show()
    else:
        if verbose:
            print('Saving plot... ', end='')
            sys.stdout.flush()
        
        fig.savefig('cpdv_dist.pdf', format='pdf', bbox_inches='tight')

        if verbose:
            print('done.')


def dir_checker(directory):
    '''
    argparse type checker that verifies that a dirname is valid and the corresponding directory contains a `cpdv_flow0.tsv` file
    '''
    if not os.path.isdir(directory):
        raise ArgumentTypeError(f'`{directory}` is not a valid directory!')
    return os.path.dirname(directory)  # this removes any trailing slashes which is nice for the plot legend


if __name__ == '__main__':
    DEFAULT_MARKER = 2.5
    DEFAULT_BINSIZE = 1
    DEFAULT_PERCENTILE = 100
    DEFAULT_FILENAME = 'cpdv_flow0.tsv'
    VERBOSE_HELP = 'print extra information to stdout'

    # note on -v: the subcommands don't inherit the -v flag, so `./cpdv_diagram.py points <file> -v` or `./cpdv_diagram.py points -v <file>`
    # would be invalid and only `./cpdv_diagram.py -v points <file>` would work. because that's not very user-friendly we need to add the -v flag
    # to each subparser. but that overrides the main parser's verbose flag (i. e. `./cpdv_diagram.py -v points <file>` would have args.verbose == False
    # because the subparser didn't receive the -v flag), so we need to store the subparser's flag under a different name
    parser = ArgumentParser(description="Generate .pdf diagrams from .tsv files generated by cpdv_gen_tsv.py.")
    parser.add_argument('-v', '--verbose', dest='verbose', action='store_true', help=VERBOSE_HELP)
    subparsers = parser.add_subparsers(required=True, title='mode', dest='mode', help='run this script with `<mode> -h` for help on the different modes')

    parser_points = subparsers.add_parser('points', help='plot the data points from each file separately')
    parser_points.add_argument('tsv_files', metavar='FILE', type=FileType('r'), nargs='+', help='a .tsv file to process')
    parser_points.add_argument('-m', '--marker', type=float, default=DEFAULT_MARKER, help=f'markersize passed to matplotlib, default {DEFAULT_MARKER}')
    parser_points.add_argument('-s', '--show', action='store_true', help='show the diagram(s) instead of writing them to a file')
    parser_points.add_argument('-v', '--verbose', dest='verbose_points', action='store_true', help=VERBOSE_HELP)

    parser_distribution = subparsers.add_parser('distribution', help='plot the distribution of packet delay in one diagram, each .tsv file in another color')
    parser_distribution.add_argument('-b', '--binsize', type=float, default=DEFAULT_BINSIZE, help=f'bin size for the histogram, default {DEFAULT_BINSIZE}')

    dist_group = parser_distribution.add_mutually_exclusive_group()
    dist_group.add_argument('-p', '--percentile', type=int, default=DEFAULT_PERCENTILE, help=f'percentile of what data should be used (e. g. 95 means that only the \
        values between the 5th and 95th percentile of the data will be considered), default {DEFAULT_PERCENTILE}')
    dist_group.add_argument('-l', '--limits', metavar='LIMIT', type=float, nargs=2, help='set the range of used values, all values below the first or above the second \
        limit will be ignored; this cannot be used together with -p and overrides the default percentile value')
    
    parser_distribution.add_argument('-c', '--noclip', action='store_false', dest='clip', help='don\'t clip values below or above the used range to the last allowed value')
    
    dir_group = parser_distribution.add_mutually_exclusive_group(required=True)
    dir_group.add_argument('-d', '--dirs', metavar='DIR', type=dir_checker, nargs='+', help='read data from cpdv_flow0.tsv from each given directory')
    dir_group.add_argument('-t', '--tsv', metavar='FILE', type=FileType('r'), nargs='+', help='read data from the given .tsv files')

    parser_distribution.add_argument('-f', '--filename', default=DEFAULT_FILENAME, help=f'change the filename used when given directories, default {DEFAULT_FILENAME}')
    parser_distribution.add_argument('-s', '--show', action='store_true', help='show the diagram instead of writing it to a file')
    parser_distribution.add_argument('-v', '--verbose', dest='verbose_distribution', action='store_true', help=VERBOSE_HELP)

    args = parser.parse_args(sys.argv[1:])  # don't pass script name to argparser

    if args.mode == 'points':
        for tsv in args.tsv_files:
            gen_plot_points(tsv, args.marker, args.show, args.verbose or args.verbose_points)
    elif args.mode == 'distribution':
        if args.tsv is not None:
            tsv_files_with_names = [(f, f.name[:-4]) for f in args.tsv]
        else:
            for d in args.dirs:
                if not os.path.isfile(os.path.join(d, args.filename)):
                    print(f'`{d}` does not contain a `{args.filename}` file!')
                    sys.exit(1)
            tsv_files_with_names = [(open(os.path.join(d, args.filename), 'r'), d) for d in args.dirs]
        gen_plot_distribution(tsv_files_with_names, args.binsize, args.percentile, args.limits, args.clip, args.show, args.verbose or args.verbose_distribution)
