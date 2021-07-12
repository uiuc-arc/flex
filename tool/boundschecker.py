#!/usr/bin/env python3
import argparse
import logging
import os
import time
from typing import List

import numpy as np

from Logger import Logger
from assertscraper import AssertScraper
from src import Util
from src.Config import Config
from src.TestDriver import TestDriver
from src.TestInstrumentor import TestInstrumentor
from src.Util import create_new_dir, filter_asserts
from src.lib.AssertSpec import AssertSpec
from src.lib.AssertType import AssertType
from src.lib.Patch import Patch
from src.lib.TestRunResults import TestRunResults

filepath = os.path.abspath(os.path.join(
    os.path.dirname(os.path.realpath(__file__)), "../"))

PROJECT_DIR = filepath

parser = argparse.ArgumentParser(description='Flex arguments')
parser.add_argument("-r", dest="repo")
parser.add_argument('-cl', dest='classname', default=None)
parser.add_argument('-test', dest='testname', default=None)
parser.add_argument('-file', dest='filename', default=None)
parser.add_argument('-line', dest='line', default=0, type=int)
parser.add_argument('-conda', dest='conda_env', default=None)
parser.add_argument('-deps', dest='dependencies', default="numpy")
parser.add_argument('-t', dest='threads', default=0, type=int)
parser.add_argument('-bc', dest='use_boxcox', action='store_true')

args=parser.parse_args()
config=Config()
config.USE_BOXCOX = args.use_boxcox
print(args)


# start time
global_start = time.time()
#libs = libraries.LIBRARIES
#library = [k for k in libs if k.name == args.repo][0]

lib_log_dir = create_new_dir("{0}/tool/logs".format(PROJECT_DIR), "bounds_", '_' + args.repo)
lib_logger = Logger(lib_log_dir)
lib_logger.logo("Testing library [%s]" % args.repo)
threads = args.threads if args.threads > 0 else config.THREAD_COUNT

# mine assertions
assert_scraper = AssertScraper("{0}/projects/{1}".format(PROJECT_DIR, args.repo), libraryname=args.repo,
                               loglevel=logging.DEBUG)
assert_scraper.parse_test_files()

assertion_specs: List[AssertSpec] = assert_scraper.asserts

# filtering asserts
assertion_specs = filter_asserts(assertion_specs,
                                 classname=args.classname,
                                 testname=args.testname,
                                 filename=args.filename,
                                 lineno=args.line)

if len(assertion_specs) == 0:
    lib_logger.logo("No assertions found")
    exit(1)

lib_logger.logo("Rundir: %s" % lib_log_dir)
conda_env = args.conda_env if args.conda_env is not None else args.conda_env
fixed_asserts = 0
tightened_asserts = 0
loosened_asserts = 0
total_asserts = 0
failed_asserts = 0
deltas = 0
notconverged = 0
estimated_ppfs = 0
errored=0
restored = False
for i, spec in enumerate(assertion_specs):
    # instrument the test
    if spec.assert_type == AssertType.ASSERTEQUAL or spec.assert_type == AssertType.ASSERT_EQUAL:
        lib_logger.logo("...Skipping...")
        continue

    total_asserts += 1

    lib_logger.logo(">>>Spec %d " % (i + 1))
    lib_logger.logo(spec.print_spec())
    assert_time_start = time.time()
    try:
        instrumentor = TestInstrumentor(spec, logstring='log>>>', deps=args.dependencies.split(","))
        instrumentor.instrument()
        instrumentor.write_file()
        restored = False
        # samples values from test
        testdriver = TestDriver(spec,
                                parallel=True,
                                condaenvname=conda_env,
                                rundir=lib_log_dir,
                                libdir=PROJECT_DIR,
                                threads=threads,
                                config=config,
                                logger=lib_logger,
                                test_timeout=500)
        test_results:TestRunResults = testdriver.run_test_loop()
        extracted_outputs = test_results.extracted_outputs
        parse_errors = test_results.parse_errors
        # save a copy of file and restore original file
        instrumentor.restore_file(testdriver.logdir)
        restored = True
        # actual value index
        avi = 1 if spec.reverse else 0
        # expected value index
        evi = 0 if spec.reverse else 1
        err = False
        assert_is_tight = False

        if test_results.dist_names is not None and len(test_results.dist_names) > 0 and test_results.dist_names[-1] == 'delta':
            bound, expected = np.inf, np.inf
            lib_logger.logo("Delta distribution.. skipping")
            deltas+=1
        elif extracted_outputs is not None:
            # compute distribution
            if Util.is_max_bound(spec):
                bound = test_results.avg_ppfs[-1]
                expected = [extracted_outputs[i][evi] for i in range(len(extracted_outputs)) if
             parse_errors[i] == 0]
                expected = np.max(Util.flatten(expected))
            else:
                bound = -test_results.avg_ppfs[-1]
                expected = [extracted_outputs[i][evi] for i in range(len(extracted_outputs)) if
                                   parse_errors[i] == 0]
                expected = np.min(Util.flatten(expected))

            if not test_results.convergences[-1]:
                notconverged += 1
                lib_logger.logo("Not converged")


            lib_logger.logo("Bound: {0}\nExpected: {1}".format(bound, expected))
            lib_logger.logo("Gap: {0}".format(expected - bound))
        else:
            bound, expected = np.inf, np.inf
            lib_logger.logo("Test runs failed")


        if np.isinf(bound):
            lib_logger.logo("Error: {0},{1}".format(expected, bound))
            err = True
            failed_asserts += 1
        elif expected == bound:
            lib_logger.logo("Expected is equal to bound: {0} == {1}".format(expected, bound))
            err = True
        elif Util.is_max_bound(spec):
            if expected < bound:
                lib_logger.logo("Expected is lower than upper bound: {0} <= {1}".format(expected, bound))
                assert_is_tight = True
        elif Util.is_min_bound(spec):
            if expected > bound:
                lib_logger.logo("Expected is greater than lower bound: {0} >= {1}".format(expected, bound))
                assert_is_tight = True
        else:
            lib_logger.logo("Error: Missing max/min bound for assert")
            lib_logger.logo(spec.print_spec())
            err = True
            failed_asserts += 1

        if not err:
            suffix = "l" if assert_is_tight else "t"
            if test_results.convergences[-1] is False:
                suffix = suffix + "e"
            # create patches/alternate files
            patch = Patch(bound, spec, extracted_outputs)
            diff, modified_file = patch.get_diff()
            if assert_is_tight:
                lib_logger.logo("Patch: Generating looser patch")
                loosened_asserts += 1
            else:
                lib_logger.logo("Patch: Generating tighter patch")
                tightened_asserts += 1

            # ppf+1%
            new_file_path = "{0}/{1}.patch_{2}".format(testdriver.logdir, os.path.basename(spec.test.filename), suffix)
            diff.apply_diff(new_file_path)
            patch_file_path = "{0}/{1}.diff_{2}".format(testdriver.logdir, os.path.basename(spec.test.filename), suffix)
            diff.to_str(patch_file_path)
            lib_logger.logo(patch_file_path)
            lib_logger.logo("Diff generated:")
            lib_logger.logo(new_file_path)
            fixed_asserts += 1
        assert_time_stop = time.time()
    except Exception as e:
        import traceback
        traceback.print_exc()
        lib_logger.logo(e)
        if not restored:
            try:
                instrumentor.restore_file(testdriver.logdir)
            except:
                pass
    finally:
        assert_time_stop = time.time()
        lib_logger.logo("Assert-Time: {:.2f}s".format(assert_time_stop-assert_time_start))
        lib_logger.logo("========================================================")

global_stop = time.time()
lib_logger.logo("Fixed asserts: {0}/{1}:{2}".format(fixed_asserts, total_asserts, (fixed_asserts+0.0)/total_asserts))
lib_logger.logo("Tightened asserts: {0}".format(tightened_asserts))
lib_logger.logo("Loosened asserts: {0}".format(loosened_asserts))
lib_logger.logo("Failed asserts: {0}".format(failed_asserts))
lib_logger.logo("Deltas : {0}".format(deltas))
lib_logger.logo("Not converged : {0}".format(notconverged))
lib_logger.logo("Estimated ppfs: {0}".format(estimated_ppfs))
lib_logger.logo("Total Time: {0:.2f}s".format(global_stop-global_start))