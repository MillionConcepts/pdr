README.md
## The Planetary Data Reader (pdr)

This tool provides a single command---`read(‘/path/to/file’)`---for ingesting
_all_ common planetary data types. It reads almost all "primary observational 
data" products currently archived in the PDS (under PDS3 or PDS4), and the 
fraction of products it does not read is continuously shrinking.
[Currently-supported datasets are listed here.](docs/supported_datasets.md) 

If the software fails while attempting to read from datasets that we have 
listed as supported, please submit an issue with a link to the file and 
information about the error (if applicable). There might also be datasets that 
work but are not listed. We would like to hear about those too. If a dataset 
is not yet supported that you would like us to consider prioritizing, 
[please fill out this request form](https://docs.google.com/forms/d/1JHyMDzC9LlXY4MOMcHqV5fbseSB096_PsLshAMqMWBw/viewform).

### Attribution
If you use _pdr_ in your work, please cite us using our Zenodo DOI: [![DOI](https://zenodo.org/badge/266449940.svg)](https://zenodo.org/badge/latestdoi/266449940)

### Installation
_pdr_ is now on `conda` and `pip`. We recommend (and only officially support) 
installation into a `conda` environment. You can do this like so: 

```
conda create --name pdrenv
conda activate pdrenv
conda install -c conda-forge pdr
```
The minimum supported version of Python is _3.9_.

Using the conda install will install all dependencies in the environment.yml 
file (both required and optional) for pdr. If you'd prefer to forego the 
optional dependencies, please use minimal_environment.yml in your 
installation. This is not supported through a direct conda install as 
described above and will require additional steps. Optional dependencies 
and the added functionality they support are listed below:

  - `pvl`: allows `Data.load("LABEL", as_pvl=True)`, which will load PDS3 
     labels as `pvl` objects rather than plain text
  - `astropy`: adds support for FITS files
  - `jupyter`: allows usage of the Example Jupyter Notebook (and other jupyter 
     notebooks you create)
  - `pillow`: adds support for TIFF files and browse image rendering
  - `matplotlib`: allows usage of `save_sparklines`, an experimental browse 
    function

### Usage

You can check out our example Notebook on a JupyterLite server for a 
quick interactive demo of functionality: 
[![JupyterLite](docs/jlitebadge.svg)](https://millionconcepts.github.io/jlite-pdr-demo/)

Additional information on usage including examples, output data types, notes 
and caveats, tests, etc. can now be accessed in our documentation on 
readthedocs at: https://pdr.readthedocs.io [![Documentation Status](https://readthedocs.org/projects/pdr/badge/?version=latest)](https://pdr.readthedocs.io/en/latest/?badge=latest)


### Contributing

Thank you for wanting to contribute to `pdr` and improving efforts to make 
planetary science data accessible. Please review our code of conduct before
contributing. [![Contributor Covenant](https://img.shields.io/badge/Contributor%20Covenant-2.1-4baaaa.svg)](docs/code_of_conduct.md)

If you have found a bug, a dataset that we claim to support that's not opening
properly, or you have a feature request, please file an issue. We will also
review pull requests, but would probably prefer you start the conversation with
us first, so we can expect your contributions and make sure they will be within
scope.

If you need general support you can find us on [OpenPlanetary Slack](https://app.slack.com/client/T04CWPQL9/C04CWPQM5)
or feel free to [email](mailto:sierra@millionconcepts.com) the team.

---
This work is supported by NASA grant No. 80NSSC21K0885.
