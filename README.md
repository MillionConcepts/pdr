## The Planetary Data Reader (PDR)
This tool will provide a single command ('read([filename])') for ingesting _all_ common planetary data types. It is currently in development. The supported data types / sets are listed below. There might be data types / sets that work but are not listed. There are also likely to be some files in the 'supported' data types / sets that break. In either of these cases, please submit an issue with a link to the file and information about the error (if applicable).

### Usage
Just run `import pdr` and then `pdr.read(filename)` where _filename_ is the full path to an data product _or_ a metadata / label file (e.g. with extensions of .LBL, .lbl, or .xml). The `read()` function will look for the corresponding data or metadata file in the same path. It returns an object containing all of the data and metadata.

The object uses the name of the data type as provided in the metadata. For example, PDS3 images are typically defined as "IMAGE" objects in the metadata, so it the data would be contained `pdr.read(filename).data.IMAGE`. The "LABEL" data is typically references (as a PVL object) in `pdr.read(filename).data.LABEL`. Some PDS3 files, especially older ones, contain multiple data types. The filepath is contained in `pdr.read(filename).filename`. Suggestions on how to improve the organization of these objects is welcomed.

### Supported Data Types
1. All data archived under PDS4 standards should be fully supported. This tool simply wraps `pds4_tools`.
2. Flexible Image Transport (FITS) data should be fully supported. This tool simply wraps `astropy.io.fits`.

### Supported Data Sets
Most of these are files archived under PDS3. The standards for these files was quite flexible, as was the quality control, especially for older missions.

* Mars Science Laboratory
    * Mars Descent Imager
        * RDR
        * EDR (w/ caveat below)
    * 

### Notes and Caveats
#### Mars Science Laboratory images
The Mars Science Laboratory "raw" (EDR) images produced by the Malin Space Science Systems (MSSS) cameras, which include Mastcam, Mahli, and the Mars Descent Imager, are archived in a bespoke compressed format. These images carry the extension '.DAT' which is typically reserved for "table" style data in PDS3. Software for converting these files to more typical PDS3-style .IMG format files has been provided in the archive. If the `dat2img` script is compiled in a directory called "MMM_DAT2IMG" under the "pdr" directory, then the `read()` action will run this script and read the resulting output. Otherwise it will just return an error. Functionality is planned to either include / compile this code with the installation of this package or (much better) to port `dat2img` to pure Python. Help is welcomed with either of these efforts! The MSL "calibrated" (RDR) files should all work fine, though.