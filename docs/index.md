# Welcome to the Planetary Data Reader (pdr)

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

Using the conda install will install some optional dependencies in the environment.yml 
file for pdr including: `astropy` and `pillow`. If you'd prefer to forego those 
optional dependencies, please use minimal_environment.yml in your 
installation. This is not supported through a direct conda install as 
described above and will require additional steps. Optional dependencies 
and the added functionality they support are listed below:

  - `pvl`: allows `Data.load("LABEL", as_pvl=True)`, which will load PDS3 
     labels as `pvl` objects rather than plain text
  - `astropy`: adds support for FITS files
  - `jupyter`: allows usage of the Example Jupyter Notebook (and other jupyter 
     notebooks you create)
  - `pillow`: adds support for reading a variety of 'desktop' image formats 
    (TIFF, JPEG, etc.) and for browse image rendering
  - `Levenshtein`: allows use of `metaget_fuzzy`, a fuzzy-matching metadata 
    parsing function

For pip users, no optional dependencies will be packaged with pdr. The extras 
tags are:
  - pvl = ['pvl']
  - fits = ['astropy']
  - notebooks = ["jupyter"]
  - pillow = ['pillow']
  - fuzzy = ['Levenshtein']

Example syntax for using pip to install syntax with `pvl` and `jupyter` optional
dependencies:
```
pip install pdr[pvl, notebooks]
```

### Usage

You can check out our example Notebook on a JupyterLite server for a 
quick interactive demo of functionality: 
[![JupyterLite](docs/jlitebadge.svg)](https://millionconcepts.github.io/jlite-pdr-demo/)

Just open a python shell and run `import pdr` and then `pdr.read(filename)`, 
where _filename_ is the full path to a data file _or_ a metadata / label file 
(extensions .LBL, .lbl, or .xml). `read()` will look for corresponding data 
or metadata files in the same path, or read metadata directly from the data file 
if it has an attached label.

`read` returns a `pdr.Data` object whose attributes include all the data
and metadata. Data attributes take their names directly from the product's
label. They can be accessed either as attributes or using
`dict`-style \[\] index notation. For example, PDS3 image objects are often
named "IMAGE", so you could examine a PDS3 image as an array with:
```
>>> data = pdr.read("/path/to/cr0_398560467edr_f0030004ccam02012m1.LBL")
>>> data['IMAGE']
array([[21, 21, 20, ..., 19, 19, 20],
       [21, 21, 21, ..., 19, 20, 20],
       [21, 21, 20, ..., 20, 20, 20],
       ...,
       [25, 25, 25, ..., 26, 26, 26],
       [25, 25, 25, ..., 27, 26, 26],
       [24, 25, 25, ..., 26, 26, 26]], dtype=int16)
```
Parsed metadata are stored in a `pdr.Metadata` object and exposed as the
`metadata` property of a `pdr.Data` object. You can access metadata values 
with `dict`-style \[\] index notation or the convenience method `metaget`. 
For instance:
```
>>> data.metaget('INSTRUMENT_HOST_NAME')
'MARS SCIENCE LABORATORY'
```
Some PDS products (like this one) contain multiple data objects. You can look
at all the objects associated with a product with `.keys()`:
```
>>> data.keys()
['LABEL',
 'IMAGE_HEADER',
 'ANCILLARY_TABLE',
 'CMD_REPLY_FRAME_SOHB_TABLE',
 'SOH_BEFORE_CHECKSUM_TABLE',
 'TAKE_IMAGE_TIME_TABLE',
 'CMD_REPLY_FRAME_SOHA_TABLE',
 'SOH_AFTER_CHECKSUM_TABLE',
 'MUHEADER_TABLE',
 'MUFOOTER_TABLE',
 'IMAGE_REPLY_TABLE',
 'IMAGE',
 'MODEL_DESC'] 
```

### Output data types
In general:
+ Image data are presented as NumPy `ndarray` objects.
+ Table data are presented as pandas `DataFrame` objects. 
+ Parsed label contents (metadata fields + values) are presented in a
`pdr.Metadata` object (behaves much like a `dict`).
+ Header and label contents are also presented as plain text (`str` objects) or, 
for PDS4 labels, `pds4_tools.reader.label_objects.Label` objects.
+ Other data are presented as simple python types (`str`, `tuple`, `dict`).
+ There might be rare exceptions.

### Notes and Caveats
#### Additional processing
Some data, especially calibrated image data, require the application of
additional offsets or scale factors to convert the storage units to meaningful
physical units. The information on how and when to apply such adjustments is
typically stored (as plain text) in the instrument SIS, and the scale factors
themselves are often (but not always) stored in the label. Image data also 
often contain special constants (like missing or invalid data), and these 
constants are often not explicitly specified in the label. 
`pdr` is therefore not guaranteed to correctly apply -- or even know 
anything about -- these constants.

`pdr.Data` objects offer a convenience method that attempts to mask invalid
values and apply any scaling and offset specified in the label. Use it like:
`scaled_image = data.get_scaled('IMAGE')`. However, we do not perform science
validation of these outputs, so **do not trust that they are ready for
analysis** without further processing or validation. Contributions towards 
making this more effective for specific data product types are very much 
welcomed.

If you'd like to visualize the outputs that this creates, the `dump_browse`
method creates separate browse files for all currently-loaded objects 
(as .jpg, .txt., or .csv) in your working directory. Use it like: 
`data.dump_browse()`. This uses the `get_scaled` method for images and will 
also output browse products for tables and labels.

#### .FMT files
Some PDS3 table formats are defined in external reference files (usually 
with a `.FMT` extension). You can often find these in the LABEL or DOCUMENT
subdirectories of data archive volumes. If you place the relevant format
files in the same directory as the data files you are trying to read, `pdr`
will be able to use them to interpret the table data. If you attempt to read 
a table object that requires a format file that is not present, `pdr` will
not be able to open the table object, and will throw a warning that includes 
the format file name in order to help you go find it. Future functionality 
may make this process smoother.

#### Data attribute naming
The observational and metadata attributes (or keys) of `pdr.Data`
objects take their names directly from the metadata files. We believe that
maintaining this strong correlation between the representation of the data
in-language and the representation of the data in-file is important, even when
it causes us to break strict PEP-8 standards for attribute capitalization.
There are three exceptions at present:
1. Some table formats include repeated column names. For usability and
compatibility, we force these to be unique by suffixing 0-indexed increasing
integers. So a table definition with two separate columns named "COLUMN" will 
return a pandas DataFrame with columns named "COLUMN_0" and "COLUMN_1."
2. PDS3 data object names sometimes contain spaces. _pdr_ replaces the spaces
with underscores in order to make them easily usable as Python attributes.

#### PDS4 products
`pdr.Data` vendors [`pds4_tools`](https://github.com/Small-Bodies-Node/pds4_tools/) 
to read PDS4 products. All valid PDS4 products should be fully supported. `pdr`
modifies some `pds4_tools` outputs in order to provide interface and behavior
consistency. In general, you should be able to use `pdr` with PDS4 products 
the same way you do with PDS3 products.

Some PDS data products have both PDS3 and PDS4 labels. Data object names, 
metadata, and even data field names and format specifications often differ 
slightly between these labels, so `pdr.Data` may produce different outputs
depending on which label you use to initialize it. This is not a bug. 
However, in general, if a PDS3 label is available, we recommend initializing 
the object from the PDS3 label rather than the PDS4 label.

#### FITS files

`pdr.Data` wraps [ `astropy.io.fits` ](https://github.com/astropy/astropy/tree/main/astropy/io/fits)
to read data from FITS files. `pdr` converts objects produced by`astropy` to 
`np.ndarrays` (FITS arrays and compressed arrays), `pd.DataFrames` (FITS ASCII 
and binary tables), or `MultiDicts` (FITS headers), so you do not need to 
change your code simply because a file is in FITS format. 

Whenever you load a data object from a FITS file, `pdr` also places the associated 
FITS header in a key of your `Data` object named "$objectname_HEADER" -- for instance, 
if you load an object named "HK_TABLE", its FITS header will appear in 
`Data.HK_TABLE_HEADER`. You can also use that name to directly load the header *without* 
loading the entire data object. 

`pdr`'s FITS-loading behavior is somewhat different depending on whether a PDS3 label, 
a PDS4 label, or no PDS label is present:

##### FITS with no PDS label

`pdr` has 'first-class' support for FITS files and does not require a PDS 
label to open them. This gives FITS users access to all of the `pdr` convenience 
functions and idioms even if no PDS labels are available.

`pdr` names data objects in FITS files opened 'directly' by FITS extension 
names (EXTNAME) when specified, and by extension types ('PRIMARY', 
'COMPRESSED_IMAGE', etc.) when not. Like duplicate objects in PDS products, 
`pdr` disambiguates duplicate names by appending integers.

 Note that any time you pass a FITS file to `pdr`
and there is no PDS label in that file's directory, `pdr` will default to this behavior. 
Conversely, if you'd like to force pdr to open a file 'directly' from its FITS
headers, but there _is_ a PDS label in its directory, simply specify that the FITS 
file is also the label file, like:

`pdr.read('name_of_data_file.fits', label_fn='name_of_data_file.fits')`.

##### With PDS3 labels

`pdr` prefers the data specification given in FITS headers to the data 
specification in the PDS3 label, with one exception: it uses object names 
from the PDS3 label. In our experience, because FITS is more rigorously 
standardized than PDS3, using the FITS header is more reliable.
Note that in some cases, PDS3 and FITS specifications may differ, even when the 
specification in the PDS3 label is technically valid. For instance, column 
names might be given differently in the FITS header, or a PDS3 TABLE might 
be stored as a FITS array HDU.

##### With PDS4 labels

Because PDS4 is more reliable and rigorously standardized than PDS3, `pdr` 
prefers the specification given in PDS4 labels to the specification given in 
FITS headers. You can always override this by passing the `label_fn` 
argument.

#### Lazy loading
Because many planetary data objects are very large, `pdr` helps conserve 
your time and memory by loading them lazily. It loads data objects into memory
when they are explicitly referenced, not when `pdr.Data` is initialized. 
For example, referencing`data.IMAGE` will immediately load the IMAGE object if 
it has not already been loaded. Alternatively, you can load objects by using 
the `load` method, like `data.load("IMAGE")`. You can also pass the 'all' 
argument to load all data objects, like `data.load("all")`. 

#### Missing files
If a file referenced by a label is missing, *pdr* will throw warnings and
populate the associated attribute from the portion of the label that mentions
that file. You are most likely to encounter this for DESCRIPTION files in
document formats (like .TXT). These warnings do not prevent you from using
objects loaded from files that are actually present in your filesystem.

#### Big files (like HiRISE)
`pdr` currently performs no special memory management, so use caution 
when attempting to read very large files. We intend to implement memory
management in the future.

#### WSL
`.jp2` support is not guaranteed for WSL (Windows Subsystem for Linux). It is supported 
on Windows itself and Linux. 

### Tests

#### Philosophy
Our testing strategy focuses on end-to-end systems integration testing to 
ensure consistency, coverage of supported datasets, and (to the extent we can 
verify it) correctness of output. We prioritize this kind of testing because 
`pdr` is intended to work with a wildly diverse body of data. Most of 
`pdr`'s source code is highly multifunctional, designed to accept format 
ambiguity and unexpected inputs. 

This means that obtaining *meaningful* coverage from unit tests is 
extremely difficult. _No written standard is reliable: the products are the 
only reliable representation of the products_.  Describing their 
idiosyncracies well enough to test against them requires replicating a 
representative subset of the data corpus and verifying that `pdr` behaves 
consistently when executed on this subset.

#### `ix`
This is exactly what our application `ix` is designed to facilitate. 
It serves both as a regression testing framework and a development tool. 
Although it serves as `pdr`'s primary test suite, it is really a distinct 
application, so it lives in a different repository: [pdr-tests](https://github.com/MillionConcepts/pdr-tests). Note 
that `ix` is feature-complete and stable, but lacks comprehensive user-facing 
documentation.

#### Unit Tests
All this being said, many potential bugs in `pdr` _are_ detectable by 
unit testing on simple cases, and although `ix` is well-optimized, running a 
comprehensive regression test against >100 GB of data products is simply not 
a fast affair. For these reasons, `pdr` also features a small suite of unit 
tests. You can run them by executing `pytest` from the repository root.

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
#### Funding Acknowledgement
This work is supported by NASA grant No. 80NSSC21K0885.
