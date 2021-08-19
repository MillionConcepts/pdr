## The Planetary Data Reader (pdr)
This tool will provide a single command---`read([filename])`---for ingesting _all_ common planetary data types. It is currently in development. Any kind of "primary observational data" product currently archived in the PDS (under PDS3 or PDS4) should be covered eventually, as should many common data types used in research workflows that do not appear in the PDS (e.g. ISIS Cube, GeoTIFF, ...) The supported data types / sets are listed below. There might be data types / sets that work but are not listed. There are also likely to be some files in the 'supported' data types / sets that break. In either of these cases, please submit an issue with a link to the file and information about the error (if applicable).

### Installation
_pdr_ is not yet on `pip` or `conda`. You can install it with a command like the following:

    pip install git+https://github.com/MillionConcepts/pdr.git

The minimum supported version of Python is _3.8_. A fresh conda environment may prevent headaches.

### Usage
Just run `import pdr` and then `pdr.read(filename)` where _filename_ is the full path to an data product _or_ a metadata / label file (e.g. with extensions of .LBL, .lbl, or .xml). The `read()` (or alias `open()`) function will look for the corresponding data or metadata file in the same path. It returns an object containing all of the data and metadata.

The returned object uses the name of the data type as provided in the metadata. For example, PDS3 images are typically defined as "IMAGE" objects in the metadata, so it the data would be contained `pdr.read(filename).IMAGE`. The "LABEL" data is typically references (as a PVL object) in `pdr.read(filename).LABEL`. Some PDS3 files, especially older ones, contain multiple data types. Suggestions on how to improve the organization of these objects is welcomed.
The object can also be treated _sort of_ like a `dict()` with the observational data and metadata attributes as keys. So, for example, `pdr.read(filename).keys()` might return `['IMAGE','LABEL']`, and then the image array can be accessed with `pdr.read(filename)['IMAGE']`. Checking the `keys()` of the returned object is often a good first thing to do.

### Output data types
In general:
+ Image data will be represented as `numpy` arrays.
+ Table data will be represented as `pandas` DataFrames.
+ Header and label data will be represented as _either_ `pvl` objects or fitsio objects, depending on the data type.
+ Other data will be represented as simple python types (e.g. strings, tuples, dicts).
+ There might be rare exceptions.

### Supported Data Types
1. All data archived under PDS4 standards should be fully supported. This tool simply wraps `pds4_tools`.
2. Flexible Image Transport (FITS) data should be fully supported. This tool simply wraps `astropy.io.fits`.
3. Many but not all data archived under PDS3 are currently supported. Older files formats are less likely to work correctly.
   + Some PDS3 table data are defined in external reference files (usually with a `.FMT` extension). If this file exists in the same directory as the data being read, then it should work. Future functionality will make this smoother.
4. The **GeoTiff format is not supported**, but the plan is to include this functionality (and a lot of others!) by wrapping GDAL.
5. The **ISIS Cube format is partly supported**, but maybe not reliably or correctly.
    
### Other Notes and Caveats
#### Additional processing
Some data, especially calibrated image data, might require the application of additional offsets or scale factors to convert the storage units to meaningful physical units. The information on how and when to apply such adjustments is typically stored (as plain text) in the instrument SIS, and the scale factors themselves are usually stored in the label. This hasn't been implemented anywhere, because it will probably require digging into each data set individually. So **do not trust that the data output by `read()` is ready for analysis** without further processing. Contributions towards solving this problem are very much welcomed.

#### Data attribute naming
The observational and metadata attributes (or keys) on the returned data object take their name directly from from how the data objects are defined within the files themselves. This is why the key for images will often be the capitalized "IMAGE" for PDS3 data; this is how it was defined in PDS3, even though this kind of capitalization is not typical in Python. There are also data object names with intercaps like "Mossbauer_Spectrum_3". I think that maintaining this strong correlation between the representation of the data in-langauge and the representation of the data in-file is important.
There are two exception cases, at present.
1. Some table data are defined with repeating column names. These are forced to be unique by suffixing an integer that just indexes the order in which the columns occurred in the format definition. So a table defined with column names of "COLUMN" and "COLUMN" in the file label will return a table with column names of "COLUMN_0" and "COLUMN_1."
2. The data object names sometimes contain spaces. _pdr_ replaces the spaces with underscores in order to make them usable as attributes.

#### Mars Science Laboratory compressed EDR images: Currently broken.
**This isn't supported at all right now. Temporarily broken!** The Mars Science Laboratory "raw" (EDR) images produced by the Malin Space Science Systems (MSSS) cameras, which include Mastcam, MAHLI, and the Mars Descent Imager, are archived in a bespoke compressed format. These images carry the extension '.DAT' which is typically reserved for "table" style data in PDS3. Software for converting these files to more typical PDS3-style .IMG format files has been provided in the archive. If the `dat2img` script is compiled in a directory called "MMM_DAT2IMG" under the "pdr" directory, then the `read()` action will run this script and read the resulting output. Otherwise it will just return an error. Functionality is planned to either include / compile this code with the installation of this package or (much better) to port `dat2img` to pure Python. Help is welcomed with either of these efforts! The MSL "calibrated" (RDR) files should all work fine, though.


#### Detached table format files
Some PDS3 table data are defined in external reference files (usually with a `.FMT` extension). If this file exists in the same directory as the data being read, then it should work. Future functionality will make this smoother.

#### External description files
Some PDS3 labels point to external metadata "description" files (usually a `.PDF`). The current functionality is to just return the name of this file as given by the pointer, not its contents.

#### Big files (like HiRISE)
No sort of memory management or lazy-loading is implemented, so expect a crash or very slow response on most machines if you try to read very large files.

---

This work is supported by NASA grant No. 80NSSC21K0885.
