# FLEX: Fixing Flaky tests in Machine Learning Projects 

This repository provides an implementation of our paper: [FLEX: Fixing Flaky tests in Machine Learning Projects by Updating Assertion Bounds](http://misailo.web.engr.illinois.edu/papers/flex-fse21.pdf). 

FLEX uses Extreme Value Theory to determine appropriate bounds for assertions in tests for stochastic Machine Learning algorithms.

## Installing 

We recommend using a conda environment to install and use flex. 
To install the requirements, do `pip install -r requirements.txt`.

To install individual projects which contain flaky tests, use the `scripts/general_setup.sh` script. See the details in next section.

## Running Flex

Step 1: Create `projects` directory in root.

Step 2: Go to `tool/scripts` and run `bash general_setup.sh ../../projects [github-slug] [local/global] [commit]` to set up the project.

All slugs and project commits used in the paper can be found in `newbugs.csv`. `global` mode will install some system level dependencies required for some projects, may need sudo access. Use `local` to avoid installing them.

Step 3: Run `python boundschecker.py -r [repo_name] -test [test_name] -file [filename]  -line [line number] -conda [conda env name] -bc (enables boxcox transformation)` in the `tool/` directory to run FLEX for the project.

E.g., for coax:
`python boundschecker.py -r coax -test test_update -file coax-dev/coax/experience_replay/_prioritized_test.py  -line 137 -conda coax -deps "numpy" -bc`
This will produce output like...
```
Bound: 0.000794638226562553
Expected: 0.001
Expected is greater than lower bound: 0.001 >= 0.000794638226562553
Patch: Generating looser patch
<location of patch>
Diff generated:
<location of diff>
```

## Explanation of flags

- Repo Name: -r
- Test Name: -test
- File name: -file
- Class name: -cl
- Line number of assertion: -line
- Conda env name: -conda
- Enable Box-Cox optimization: -bc
- Number of threads: -t (default 1)

## Directory Structure

The source code for the project is mainly contained in the `tool/` directory. The `tool/` directory is further split into sub-directories like `src` which contains implementation files, folders with setup scripts (`scripts`), logs folders and other implementation files. The root directory further contains some top level files like `requirements.txt`.

## FLEX Configuration

The file `src/Config.py` contains all the configurations for the tool

- DEFAULT_ITERATIONS: Number of samples to collect in first round (50)
- SUBSEQUENT_ITERATIONS: Number of samples to collect in subsequent rounds (50)
- MAX_ITERATIONS: Max samples (1000)
- THREAD_COUNT: Number of threads (1)
- USE_BOXCOX: Apply boxcox transformation (False)
- BOUNDS_MAX_PERCENTILE: Max percentile to check (0.9999)
- MIN_TAIL_VALUES: Minimum tail values (50)

## Flaky Tests used in the paper

The file `newbugs.csv` contains the list of flaky test we used in our paper. Each row presents the details: filename, classname, filename, and assert line. It also contains the commit id of the repository that we used.


## Citation

If you use our tool, please cite us using:
```
@inproceedings{dutta2021flex,
  title={FLEX: Fixing Flaky Tests in Machine Learning Projects by Updating Assertion Bounds},
  author={Dutta, Saikat and Shi, August and Misailovic, Sasa},
  year={2021},
  organization={FSE}
}
```