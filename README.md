## The Planetary Data Reader (PDR)
This tool will provide a single command ('read([filename])') for ingesting _all_ common planetary data types. It is currently in development. Any kind of "primary observational data" product currently archived in the PDS (under PDS3 or PDS4) should be covered, as should many common data types used in research workflows that do not appear in the PDS (e.g. ISIS Cube, GeoTIFF, ...) The supported data types / sets are listed below. There might be data types / sets that work but are not listed. There are also likely to be some files in the 'supported' data types / sets that break. In either of these cases, please submit an issue with a link to the file and information about the error (if applicable).

### Usage
Just run `import pdr` and then `pdr.read(filename)` where _filename_ is the full path to an data product _or_ a metadata / label file (e.g. with extensions of .LBL, .lbl, or .xml). The `read()` function will look for the corresponding data or metadata file in the same path. It returns an object containing all of the data and metadata.

The object uses the name of the data type as provided in the metadata. For example, PDS3 images are typically defined as "IMAGE" objects in the metadata, so it the data would be contained `pdr.read(filename).data.IMAGE`. The "LABEL" data is typically references (as a PVL object) in `pdr.read(filename).data.LABEL`. Some PDS3 files, especially older ones, contain multiple data types. The filepath is contained in `pdr.read(filename).filename`. Suggestions on how to improve the organization of these objects is welcomed.

### Supported Data Types
1. All data archived under PDS4 standards should be fully supported. This tool simply wraps `pds4_tools`.
2. Flexible Image Transport (FITS) data should be fully supported. This tool simply wraps `astropy.io.fits`.
3. The **GeoTiff format is not supported**, but the plan is to include this functionality (and a lot of others!) by wrapping GDAL.
4. The **ISIS Cube format is not supported**, but the plan is to include this functionality by also wrapping _something_.

### Supported Data Sets (w/ Notes)
Most of these are files archived under PDS3. The standards for these files was quite flexible, as was the quality control, especially for older missions.

* Mars Science Laboratory
    * Mars Descent Imager
        * RDR data works. Uncompressed EDR works (see: caveat below).
    * Mastcam
        * RDR data works. Uncompressed EDR works (see: caveat below).
    * MAHLI
        * RDR data works. Uncompressed EDR works (see: caveat below).
* Mars Global Surveyor
    * Near Infrared Mapping Spectrometer (NIMS)
        * The image data works fine. These files contain other table data. Not all of it is supported. The "BAD_DATA_VALUES_HEADER" requires referencing the "BADDATA.TXT" metadata / format file (see: note below).
* Cassini
    * Imaging Science Subsystem (COISS)
        * WACFM
            * The image and table data contained in these files all appear to parse successfully.
        * NACFM
            * The image and table data contained in these files all appear to parse successfully.
* Viking
    * Camera_2
        * These files contain an IMAGE and a HISTOGRAM. Both appear to parse correctly.
* Mars Exploration Rover (MER)
    * APXS
        * EDR contains two tables (ENGINEERING_TABLE and MEASUREMENT_TABLE), which both appear to parse correctly.
    * Mossbauer
        * The EDR label does not seem to contain a data pointer and so **does not parse**.
    * Descent Camera
        * EDR seems to work great.
    * Hazard Avoidance Camera (Hazcam)
        * The '.rgb' files **maybe do not parse**; need to investigate what this file should actually contain.
        * The EDR and RDR '.img' files work.

[... list is in progress ...]
    


### Notes and Caveats
#### Mars Science Laboratory images
The Mars Science Laboratory "raw" (EDR) images produced by the Malin Space Science Systems (MSSS) cameras, which include Mastcam, MAHLI, and the Mars Descent Imager, are archived in a bespoke compressed format. These images carry the extension '.DAT' which is typically reserved for "table" style data in PDS3. Software for converting these files to more typical PDS3-style .IMG format files has been provided in the archive. If the `dat2img` script is compiled in a directory called "MMM_DAT2IMG" under the "pdr" directory, then the `read()` action will run this script and read the resulting output. Otherwise it will just return an error. Functionality is planned to either include / compile this code with the installation of this package or (much better) to port `dat2img` to pure Python. Help is welcomed with either of these efforts! The MSL "calibrated" (RDR) files should all work fine, though.

#### Detached table format files
Many table data in PDS3 have a format that is defined in a special file at a different location in the archive. Prototype capability for finding / reading these automatically exists, but has not been incorporated into this tool yet. So table data defined in this way are not yet supported.

#### Additional processing
Some data, especially calibrated image data, might require the application of additional offsets or scale factors to convert the storage units to meaningful physical units. This information on how and when to apply such adjustments is typically stored (as plain text) in the instrument SIS, and the scale factors themselves are usually stored in the label. This hasn't been implemented anywhere, because it will probably require digging into each data set individually. So don't trust that the data output by `read()` is automatically read for analysis. Contributions towards solving this problem are very much welcomed.

