# Datasets Supported by `pdr`

"Support" from `pdr` falls into two categories: official and notional.

**_Officially supported datasets_** have been extensively tested and all of
their products are supported. If you encounter a file of this type that does not
open with pdr, please open an issue at: 
https://github.com/MillionConcepts/pdr/issues

**_Notionally supported datasets_** have been manually tested with a small
number of files. Some of these sets do not conform to PDS standards in ways
that prevent us from ever testing them to our standard for official support 
(for instance, they might lack label files). Others in this category will be 
moved to official support after more rigorous testing.

Many datasets that do not fall into either of these categories may work
just fine. They are not listed simply because we have not had a chance to 
test them yet.

Some datasets are also **_Known unsupported_**. Some files or objects may
open, while others may not; those that do may open incorrectly. Support is
planned for some of these datasets. Others—due to unusual data formats,
availability, or quality issues—may never be supported.

**All PDS4 products, unless explictly listed here as known unsupported or specified
in [`pds4_tools`](https://github.com/Small-Bodies-Node/pds4_tools/) documentation
as out of support, are considered at least notionally supported**. We 
give specific comments and usage suggestions about some PDS4 product types below. 
PDS4 products are much more rigorously standardized and validated than PDS3 
products, allowing the `pds4_tools` developers to make very broad support 
claims that we consider trustworthy. All currently-known exceptions are due 
to data QA problems rather than deficiencies in `pds4_tools`. 

As a general note, we are less confident about products that contain raw 
telemetry (or other forms of unprocessed data) or that use bespoke compression 
schemes. Fully validating our outputs for these products would require 
recreating portions of ground processing pipelines, which is outside the scope 
of this project. "Support" for these types means that they load correctly into 
expected data structures and that interpretable portions of their data
(like timestamps) appear to match other sources.


## Officially Supported Datasets:
#### Apollo
  - all PDS3 datasets that have not been deprecated by PDS4 versions. 
    specifically:
    - Apollo 12 and 15 Solar Wind Spectrometer tables
    - Apollo 15 and 16 X-ray Fluorescence Spectrometer tables
    - Apollo 14 and 15 Cold Cathode Ion Gage digitized plots and index tables
    - Apollo 15 and 16 Lunar Self-Recording Penetrometer transcribed tables
    - BUG soil reflectance tables
    - Apollo 15, 16, and 17 Metric Camera images
    - Apollo 17 Traverse Gravimeter Experiment
#### Cassini
  - CAPS EDRs, RDRs, and DDRs
  - CDA
    - DA area, counter, events, settings, signal, spectra peaks, and status history tables
      - *Note: Many of the spectra products are placeholder tables composed of
        missing data constants. These placeholders are not supported.* 
    - HRD raw and processed data
  - CIRS TSDR spectra and navigation/housekeeping data
  - CIRS reformatted products at the RMS node (calibrated spectra)
  - INMS level 1A products and housekeeping data
  - ISS EDRs, MIDRs, and calibration data
  - MAG REDRs, RDRs, and most housekeeping data
  - MIMI EDRs and RDRs
  - RADAR ABDR, ASUM, BIDR, LBDR, SBDR, and STDR
  - RPWS REFDRs, RDRs, and DDRs
    - *Note: The RDR LRFULL tables include a MINI_PACKET_HEADER column which 
       uses an illegal data type and cannot be parsed.*
  - RSS gravity, occultation, solar, and bistatic experiments
  - RSS ancillary products: ODF, TDF, TLM, 158, and 515
  - Saturn rings occultation profiles derived from RSS, UVIS, and VIMS data
  - Saturn small moon and Gaskell shape models
  - UVIS EUV, FUV, and HDAC products
  - VIMS EDR cubes (PDS4 labels only)
  - All Huygens Probe data except DISR IR tables
#### Chandrayaan-1
  - M3 L0, L1B, and L2 images and ancillary files 
  (*note: L0 line prefix tables are not currently supported*)
#### Clementine
  - Map-projected Basemap, HiRes, NIR, and UVVIS mosaics
    - These have been migrated to PDS4, pending archive approval.
  - Gravity and topography derived products
  - LWIR RDRs
  - RSS bistatic radar RDRs
  - LIDAR data *note: This is a saved PDS data set, not a regular PDS archive, 
    but it can be opened with `pdr`*
#### Comet D/Shoemaker-Levy 9/Jupiter Impact Observing Campaign
  - GIC ground-based observations
  - AAO image cubes
  - Photometry of Io and Europa during SL9 flashes
  - ESO
    - EMMI images
    - IR spectra
    - SUSI images
  - IRTF NSFCAM images
  - MSSSO CASPIR images
  - OAO OASIS IR images
  - HST images
  - IUE spectra
  - Galileo Orbiter
    - NIMS tables
    - PPR EDRs
    - SSI REDRs (images only)
    - UVS EDRs and RDRs
#### Dawn
  - Framing Camera: EDRs, RDRs, mosaics, shape models, and most calibration images
  - VIR: mosaics, EDR and RDR cube products
  - RSS: gravity models
#### Deep Impact
  - HRI-IR raw and reduced/calibrated spectra
  - HRI-VIS raw and calibrated images
  - MRI-VIS raw and calibrated images
  - ITS-VIS raw and calibrated images
  - Raw and calibrated navigation images (HRI-VIS, MRI-VIS, and ITS-VIS)
  - Derived products: shape models, surface temperature maps, and MRI-VIS photometry data
  - Pre-launch testing data
  - Radio science ODF files
  - Spacecraft instrument temperature data
  - IRAS and ground-based supporting observations
#### Deep Space 1
  - IDS RDRs
  - MICAS DEM, images, and matrices
#### EPOXI
  - HRI-IR raw and calibrated spectra
  - HRI-VIS raw and calibrated images
  - MRI-VIS raw and calibrated images
  - Derived products: shape models, HRI-VIS deconvolved images, photometry 
    data, and stellar PSFs
  - In-flight calibration images
  - Spacecraft instrument temperature data
#### Galileo 
  - EPD: calibrated Jupiter data (PDS4) and pre-Jupiter products (PDS3)
  - GDDS tables 
  - HIC tables *note: Only the PDS4 versions have been tested here*
  - MAG tables (except summary tables)
  - NIMS: Pre-Jupiter EDRs, SL-9 fragment impact tables, and Ida/Gaspra-specific
    data products at SBN
  - PLS: calibrated/derived Jupiter data (PDS4) and pre-Jupiter products (PDS3)
  - PPR: EDRs and RDRs
  - PWS: REDRs (ASCII versions), DDRs, and SUMM products
  - RSS: Jupiter and Io ionosphere electron density profiles
  - SSD: derived electron flux data
  - SSI: 
    - Calibration images
    - REDRs (images only)
    - Ida/Gaspra specific data products at SBN
  - UV: UVS and EUV *note: They open correctly from their PDS4 labels, but the 
    PDS3 labels are currently unsupported.*
  - Probe datasets: ASI, EPI, HAD, LRD, NEP, NFR, and most DWE and NMS products
  - Trajectory data
#### Giotto
  - DID RDRs
  - GRE RDRs
  - HMC RDRs
  - IMS HIS and HERS RDRs
  - JPA DDRs
  - MAG RDRs
  - NMS ion and neutral gas RDRs
  - OPE RDRs 
  - PIA
#### GRAIL
  - LGRS RDR: SHADR, SHBDR, and RSDMAP
  - RSS: BOF, ODF, OLF, and RSR
#### GRSFE
  - Airborne datasets: ASAS, AVIRIS, and TIMS images; AVIRIS and TIMS tables
  - Ground-based datasets: GPS profiles, helicopter stereo profiles, spectral 
    hygrometer, PARABOLA, PFES, reagan radiometer, wind experiment, and weather 
    station data
#### ICE
  - EPAS, MAG, PLAWAV, RADWAV, ULECA, and SWPLAS
  - ICI text files
  - ephemeris products
#### IHW
  - AMSN Halley visual data
  - ASTR Halley observations from 1835 and 1910, and Giacobini-Zinner data
  - IRSN Halley images, tables and spectra, and Giacobini-Zinner images
  - LSPN Halley images, and subsampled Giacobini-Zinner images
  - MSN radar and visual tables
  - NNSN Halley addenda images, and Giacobini-Zinner images
  - PPN Halley flux, magnitude, polarimetry, and stokes parameter data
  - SSN
    - Halley calibrated 1D spectra, and raw and calibrated 2D spectral images
    - Giacobini-Zinner raw 2D spectral images
  - RSN Halley continuum, occultation, OH, radar, and spectral line data
  - CCD Halley outburst observations
  - *Note: most of the Halley datasets listed above are available at the SBN 
    in 2 versions. Version 2.0 tends to open better with `pdr` and in a more 
    user-friendly format. When V2.0 is available, V1.0 should be considered 
    notionally supported.*
#### IUE
  - Raw and extracted spectra
  - Most image products
#### Juno
  - FGM tables
  - Gravity Science tables (EDR, RSR, and TNF)
  - JADE EDRs, RDRs, and derived moments 
  - JEDI EDRs and RDRs
  - JIRAM EDRs and RDRs *note: RDRs may not read correctly from their PDS4
  labels. We recommend opening them from their PDS3 labels.*
  - JunoCam EDRs, RDRs, and maps
  - MWR EDRs and RDRs *Note: performance is better if read from the PDS3 labels. 
    This requires .FMT (format) files, available in the root directories of the 
    MWR volumes.*
  - Waves RDR 'Burst' tables
#### LOIRP
  - Lunar Orbiter 1-5 EDRs 
#### Kaguya/Selene
  - Spectral Profiler data
  - other datasets have been migrated to PDS4 and are notionally supported
#### Lunar Prospector
  - PDS3 datasets that have not been deprecated by PDS4 versions. specifically:
    - LOSAPDR
    - ER: RDR, SUMM, and level 2 products
    - MAG: SUMM, and level 2, 3, and 4 products
    - Level 0: attitude, trajectory, and command products
#### LRO
  - CRaTER EDR secondary science and housekeeping tables, CDR, and DDR
  - DIVINER
    - EDR and RDR tables
    - L2 and L3 GDR images/backplanes
    - L4 tables
  - LAMP 
    - EDR and RDR (except acquisition list tables and spectral image 'door open' 
      headers)
    - GDR
  - LEND EDR and RDR
  - LOLA RDR (*note: other LOLA datasets have been migrated to PDS4 and are 
    notionally supported*)
  - LROC
    - WAC EDR and CDR
    - NAC EDR, CDR, and raw image data (NACR and NACL in image name)
    - NAC DTM
    - WAC Derived products: EMP, HAPKE, HAPKE PARAMMAP, ORBITS, POLE ILL, TIO2
  - Mini-RF
    - Bistatic Radar EDR, RDR, and DDR
    - Global mosaics
    - SAR level 1 and level 2 data, and polar mosaics
  - Radio Science RANGE, SFF, TRK, and WEA
#### Lunar Radar (Earth-based)
  - 70 cm radar maps
  - 12.6 cm (S-band) backscatter maps
  - south pole DEM
#### Lunar Spectroscopy (Earth-based)
  - RELAB spectra
#### Magellan
  - FMAPs
  - Stereo-Derived Topography
  - C-BIDR images *note: `pdr` reads these correctly according to the 
    specifications in the labels, but there are unaccounted-for offsets in the
    images.*
  - F-MIDR and C-MIDR
  - GxDR: GTDR, GEDR, GSDR, and GREDR
  - GVDR
  - BSR raw data and calibrated spectra
  - LOSAPDR
  - Spherical Harmonic, Topography, and Gravity models and maps
  - Occultation raw data and derived profiles
  - Radio Tracking Data (except ODF3B tables)
  - RSS solar wind experiment ('safed' dataset)
#### Mariner 9
  - IRIS data
  - RSS electron density profiles
  - Cloud catalog
  - ISS images
#### Mars Express
  - MARSIS EDRs and RDRs
  - ASPERA EDRs, RDRs, and DDRs
  - HRSC REFDRs, and SRC RDRs
  - PFS raw interferograms, and housekeeping tables
  - SPICAM UV and IR RDRs
  - MRS L1B and L2 products, and derived profiles
  - MRS L1A RSR tables (except the "SAMPLE WORDS" field) and most ODF tables
  - OMEGA derived global maps and hydrous sites
#### Mars Odyssey
  - THEMIS 
    - spectral qubes: VIS and IR v2 geoprojected images, VIS EDR and RDR,
      IR EDR
      - *note: ISIS history and header objects are not supported. Also, some
        products have sideplanes giving destripe metadata; these sideplanes 
        are discarded rather than returned to the user.* 
    - derived products: BTR, ABR, PBT, and ALB
  - MARIE/MAR REDRs and RDRs
  - GRS suite
    - GRS EDRs, corrected spectra, and summed spectra
    - NS EDRs, averaged spectra, and derived data
    - HEND EDRs, averaged spectra, and derived data
    - Element concentration maps
    - special data products
    - improved derived neutron data (PDS4)
  - RSS ODF, RSR, and TDF products
#### Mars Pathfinder
  - IMP EDRs
  - RVRCAM EDRs and MIDRs
  - APXS EDRs and DDRs
  - Stereo-derived 3D position data
  - Radio science ODFs, TDFs, reduced tracking data, and estimated Mars rotation 
    parameters
  - Engineering EDRs and RDRs
#### MER 1 and 2
  - Hazcam operations EDRs, RDRs, and mosaics
  - Navcam operations EDRs, RDRs, and mosaics
  - Pancam operations EDRs, RDRs, and mosaics
  - Microscopic Imager operations EDRs, RDRs, and mosaics
  - Descent Camera EDRs
  - RSS UHFD tables and most ODFs
#### MESSENGER
  - GRNS
    - NS EDR, CDR, DDR
    - GRS EDR, RDR, CDR, DAP
  - MASCS
    - UVVS EDR, CDR, DDR, and models
    - VIRS EDR, CDR, DDR, and DAP
  - MLA EDR, RDR, RADR, CDR, and GDR
  - XRS EDR, RDR, and CDR
    - *note: RDR maps are defined differently in their PDS3 and PDS4 labels.
      We recommend opening them from their PDS4 labels.*
  - RSS EDR and RDR
    - *note: some EDR products (DDOR and TNF) have UNDEFINED record types in 
      their PDS3 labels. We recommend opening them from their PDS4 labels.*
  - Space Weathering maps
  - MEAP electron events tables, thermal neutron map, enhanced gamma ray 
    spectrometry data, and image cubes
  - Ground calibration data (aside from NS and MASCS)
#### MGS
  - TES-TSDR ATM, BOL, GEO, OBS, POS, TLM, IFG and RAD (fixed-length tables only)
  - TES Thermal Inertia and Albedo maps
  - MOLA PRDR, IEGDR (v1 and v2), MEGDR, and SHADR
  - RSS most Raw Data and Science Data Products (see Known Unsupported Datasets 
    below for excluded products)
  - RSS electron density profiles
  - MOC decompressed standard data products
  - MAG/ER fullword and high-res MAG data, omnidirectional and angular ER flux 
    data, and the derived magnetic field map
#### MRO
  - CRISM EDR, CDR, DDR, LDR, TER, TRDR, MRDR, and MTRDR
  - CRISM speclib and typespec tables
  - SHARAD EDR and RDR (*Note: PDR will only read the "science data" column(s) 
    of the EDR science telemetry tables, not the columns described in 
    science_ancillary.fmt, which may or may not actually exist.*)
  - SHARAD rgram and geom files
  - RSS ODF, RSR, RSDMAP, SHADR, SHBDR, and TPS
  - HiRISE EDRs and DTMs (*note: only the .img DTMs are officially supported*)
  - MCS EDRs and RDRs
  - CTX EDRs
  - MARCI EDRs
#### MSL
  - Hazcam EDR and RDR (including ops parameter maps)
  - Navcam EDR and RDR (including ops parameter maps)
  - Mastcam, MAHLI, and MARDI RDRs
  - CCAM LIBS EDR, L1B, and L2; CCAM RMI EDR and RDR
  - APXS EDR and RDR (*note: the EDR checksum suffix is not supported*)
  - Chemin L1B and L2 RDRs, and EDRs
  - Navcam mosaics
  - PLACES localization data and orbital maps
  - DAN EDRs and RDRs
  - SAM RDRs
  - REMS EDRs and RDRs
#### MSX
  - Infrared Minor Planet Survey
  - Small Bodies Images
  - Zodiacal Dust Data
  - QUBE images
#### NEAR
  - GRS EDRs, L2 and L3 products
  - MAG EDRs and RDRs
  - MSI raw data, IOFs, RADs, DIMs, and shape models
  - NIS EDRs and L2 products
  - NLR EDRs, CDRs, and shape models
  - RSS spherical harmonic models, gravity acceleration maps, Eros landmarks table, and ODFs
  - XRS EDRs, L2 and L3 products
#### New Horizons
  - ALICE EDRs and RDRs
  - LEISA EDRs and RDRs
  - LORRI EDRs and RDRs
  - MVIC EDRs and RDRs
  - PEPSSI EDRs, RDRs, and resampled plasma fluxes
  - REX EDRs and RDRs
    - Note, some REX files have two pointers for EXTENSION_SSR_SH_HEADER, the
      EXTENSION_SSR_SH_HEADER_0 should be disregarded (it gives info on an 
      empty table), refer only to EXTENSION_SSR_SH_HEADER_1
  - SDC EDRs and RDRs
  - SWAP EDRs and RDRs
  - Pluto encounter derived products: surface composition maps, most atmosphere 
    data, and geology/geophysical maps
#### Pioneer 10 and 11
  - GTT RDRs
#### Pioneer Venus Orbiter
  - OEFD HIRES data and 24 second averages
  - OETP HIRES and LORES electron data, bow shock and ionopause crossings, and 
    solar EUV data
  - OIMS HIRES data and 12 second averages
  - OMAG
    - P-sensor HIRES data and 24 second averages
    - Spacecraft coordinates HIRES data and 24 second averages
  - ONMS HIRES data and 12 second averages
  - ORPA processed data
  - OUVS IMIDR images
  - POS VSO coordinates
  - POS SEDR
#### Phoenix
  - TEGA EDRs (except LED tables) and most RDRs
  - MECA
    - TECP EDRs and RDRs
    - WCL EDRs and some RDRs (PT, ISE, CND)
    - AFM EDRs and RDRs
    - OM EDRs and RDRs
    - ELEC EDRs
  - SSI EDRs, RDRs, and mosaics
  - RAC EDRs, RDRs, and mosaics
  - ASE EDRs, RDS
  - Telltale Experiment (TT) products
  - Atmospheric Opacity (AO) products
  - PDS4 products: RA, MET, LIDAR, and derived products
#### Pre-Magellan collection at the GEO node
  - AIRSAR images
  - Earth-based Mars, Mercury, Lunar, and Venus observations
  - Pioneer-Venus orbiter radar and gravity tables, and most radar images
  - Viking orbiter gravity data
#### Rosetta
  - Orbiter:
    - ALICE EDRs, RDRs, and REFDRs
    - COSIMA images and data tables
    - CONSERT auxiliary tables
    - GIADA EDRs, RDRs, and DDRs
    - MIDAS RDRs and DDRs (excluding those with a .dat file extension)
    - MIRO EDRs and RDRs
    - NAVCAM EDRs and RDRs
    - OSIRIS EDRs, RDRs, DDRs, and shape models
      - *note: Images are archived in both .img and .fit file formats. The 
        .img products have attached labels, while the .fit products have detached 
        labels. When downloading the data, make sure to store these in separate 
        directories or pdr will try to open the .img products using the detached labels.*
    - ROSINA EDRs, RDRs, and DDRs
    - Rosetta Orbiter Plasma Consortium Instruments:
      - RPCICA EDRs, RDRs, REFDRs, and DDRs
      - RPCIES EDRs, RDRs, and DDRs
      - RPCLAP EDRs, RDRs, and DDRs
      - RPCMAG EDRs, RDRs, and REFDRs
      - RPCMIP RDRs
    - RSI EDRs and RDRs
    - SREM EDRs and DDRs
    - VIRTIS DDRs
  - Lander:
    - APXS EDRs
    - COSAC EDRs and RDRs
    - CONSERT auxiliary tables
    - MODULUS/Ptolemy EDRs, RDRs, and DDRs
    - MUPUS EDRs and RDRs
    - ROLIS EDRs and RDRs
    - ROMAP EDRs, RDRs, and DDRs
    - SD2 RDRs
    - SESAME EDRs and RDRs
#### Sakigake
  - IMF RDRs
  - SOW RDRs
#### Saturn RPX
  - HST images, masks, and engineering data
  - WHT images and spectra
  - IRTF images
  - CFHT images
  - WIYN images
#### Saturn Ring Occultation of 28 Sagittarii (1989)
  - Earth-based observations at RMS
#### SOHO
  - LASCO images and photometry data
#### Stardust
  - CIDA EDF and housekeeping data
  - DFMI products
  - DSE products
  - NAVCAM EDRs, RDRs, derived shape models, and pre-flight calibration images
  - SRC temperature and geometry data
  - Keck Observatory supporting observations
#### Stardust-NExT
  - CIDA
  - DFMI
  - NAVCAM EDRs and RDRs
  - Derived shape models
#### Suisei
  - Solar wind experiment RDRs
#### Vega 1 and 2
  - TVS raw, processed, and transform images
  - IKS raw and processed data
  - DUCMA data
  - SP-1 and SP-2 data
  - PM1 data
  - TN-M data
  - MISCHA data
  - Stooke Shape Models
  - Balloon and lander EDRs and RDRs 
  - PUMA mode data
#### Ulysses
  - COSPIN
  - EPAC
  - GAS (table and GIF files only)
  - GRB
  - HISCALE
  - SCE
  - SWOOPS
  - UDDS
  - URAP
  - VHM/FGM
#### Venera 15 and 16
  - ROE derived electron density profiles
#### Venus Climate Orbiter
  - IR1 and IR2 raw, calibrated, and geometry data
  - LIR raw, calibrated, and geometry data
  - UVI raw, calibrated, and geometry data
  - RS doppler and temperature-pressure profiles
#### Venus Radar Data (Earth-based)
  - Uncalibrated, Delay-Doppler Images
  - Calibrated, Multi-Look Maps
#### Viking 1 and 2
  - Lander
    - LCS image EDRs and rock data
    - Labeled release experiment
    - Seismology experiment
#### Voyager 1 and 2
  - CRS RDR and SUMM products
  - IRIS derived maps and the expanded collection of full-res Jupiter/Saturn data
  - IRIS full-res spectral observations
  - ISS uncompressed images, and ascii ancillary tables
  - LECP RDR and SUMM products (except a few 'original binary' products)
  - MAG RDR and SUMM products
  - PLS RDR and SUMM products (except a few 'original binary' products)
  - POS SUMM products
  - PRA RDR and most SUMM products
  - PWS RDR, SUMM, and DDR products
  - RSS Triton derived atmospheric profile
  - UVS reformatted airglow spectra and derived maps
  - Ring Profiles derived from ISS, PPS, UVS, and RSS data (except VAX_REAL tables)
#### WFF/ATM
  - DEM vector data tables

## Notionally Supported Datasets:
#### Apollo
  - PDS3 versions of Apollo 15 and 17 Heat Flow Experiment tables -- 
    however, we recommend using the PDS4 collection a15_17_hfe_concatenated,
    which contains corrections and additional data, instead
#### Cassini
  - CIRS spectral cubes
#### Comet D/Shoemaker-Levy 9/Jupiter Impact Observing Campaign
  - Volume sl9_0007 ground-based observations archived at ATM
#### Juno
  - JUGN EDRs *note: most will open from PDS4 .xml labels only; RSRs open more
  efficiently from PDS3 labels*
#### IHW
  - Version 1.0 of Halley data from ASTR, IRSN (except filter curves and 
    spectroscopy data), LSPN (subsampled images only), NNSN, and PPN
  - NNSN Halley images version 1.0 and 2.0 (excluding the V1.0 addenda dataset, 
    which is officially supported)
#### LROC
  - Anaglyphs
  - NAC DTM without labels (under EXTRAS folder at LROC mission node)
  - WAC derived tif files without labels (under EXTRAS folder at LROC
  mission node)
#### Mars Express
  - HRSC derived clouds data
  - PFS derived water vapor maps
  - OMEGA derived atmospheric profiles
  - VMC EDRs *note: a small subset (~3%) of the EDRs do not open because of mistakes in their labels. They are primarily from extended mission phase 2 and earlier.*
  - VMC RDRs *note: by default `pdr` returns the calibrated multi-band image layer of the FITS file. To access the raw single-band image layer we recommend using one of the methods described in the MEX VMC EAICD.*
#### MER 1 and 2
  - Many MER products have been converted to PDS4, including: 
    - APXS, Mössbauer and Mini-TES products
    - Navcam and Pancam science images
    - Pancam color mosaics
#### MRO
  - HiRISE RDRs and DTMs (the .jp2 products)
#### MSL
  - CheMin Film EDRs (have efm in filename)  
#### Rosetta
  - Orbiter:
    - VIRTIS EDRs
  - Lander:
    - ROMAP calibrated housekeeping data *Note: There are multiple format files 
      for these products that share a name but handle the data differently. If 
      there are unexpected offsets in a table, confirm you are using the correct 
      'romap_calhk.fmt' file.*

## Known Unsupported Datasets
#### Apollo
  - Lunar Sample Photographs (support planned; low priority)
#### Cassini
  - CIRS variable-length '.VAR' tables (support not planned)
  - ISS telemetry and prefix tables (support planned)
  - MAG error count housekeeping data
  - RPWS telemetry data
  - RSS ancillary products: TDF, TLM, PD1, PD2, TNF, EOP, ION, and TRO (support not planned)
  - VIMS EDR cubes (PDS3 labels; support not planned--open with PDS4 labels)
  - Huygens Probe DISR IR tables (support planned; low priority )
#### Clementine
  - Imaging EDRs (basemap, HiRes, NIR, and UVVIS) (support not planned)
  - LWIR EDRs (support not planned)
  - RSS EDRs (support not planned)
#### Comet D/Shoemaker-Levy 9/Jupiter Impact Observing Campaign
  - Galileo SSI REDR telemetry and line-prefix tables (support planned)
#### Dawn
  - Framing camera: a handful of calibration images
#### Deep Impact
  - Movies of 9P/Tempel 1 approach and encounter (support not planned; not an 
    archive-compliant format)
#### Galileo
  - MAG summary tables (other tables supported, support not planned)
  - NIMS Jupiter EDRs and cubes (support planned)
  - SSI REDR telemetry and line-prefix tables (support planned)
  - PLS EDRs (support not planned)
  - PWS EDRs, binary REDRs, and REFDRs (support planned)
#### Giotto
  - GRE EDRs (support not planned)
#### GRAIL
  - LGRS: EDR and CDR (support not planned)
  - RSS: BTM, TDM, TNF, XRF, and ancillary products (support not planned)
#### GRSFE
  - AIRSAR compressed images (support not planned)
  - AIRSAR sampler images (support planned; 8-bit VAX BYTE sample type)
  - Daedalus spectra (support not planned)
  - Directional emissivity experiment (support not planned)
  - SIRIS spectra (support not planned)
#### IHW
  - Most Giacobini-Zinner products have incomplete PDS3 labels. Text files and 
    most images will still open, but tables do not. (support not planned)
  - ASTR Halley v2.0 tables with observations from the 1980's (support planned)
  - IRSN Halley v1.0 spectroscopy and filter response curve tables (support planned)
  - LSPN compressed images in the Halley V1.0 and Giacobini-Zinner datasets (support not planned)
  - SSN 2D spectral products with SPECTRAL_IMAGE_QUBE pointers (support planned)
  - SSN 2D spectral products with typos in their filenames (support not planned)
  - RSN UV visibility products (support planned)
#### IUE
  - A handful of the image products do not open because of a typo in their 
    labels. The QUALITY_IMAGE object is written as QUALITY_QUALITY_IMAGE. (support planned)
#### Juno
  - JADE Ion sensor housekeeping data prior to arrival at Jupiter (support not planned)
  - UVS (support planned)
  - Waves EDR (support not planned) and RDR 'Survey' tables (support planned)
    - *Currently, these are available at the PPI node in .csv format and can be opened with Excel.*
#### Lunar Prospector
  - Level 0: ephemeris and position (support not planned)
  - Level 0: sun pulse and merged telemetry (support planned; low priority)
#### LRO
  - CRaTER EDR primary science data (support not planned)
  - LAMP EDR/RDR acquisition list tables and spectral image 'door open' headers (support planned)
  - Mini-RF raw SAR products (support not planned)
#### Magellan
  - C-BIDR ancillary tables (support not planned)
  - F-BIDR (support not planned)
  - ALT-EDR (support not planned)
  - ARCDR (support planned)
  - SCVDR (support not planned)
  - BSR calibrated time samples (support planned)
  - Radio Tracking ODF3B tables (support planned)
  - SAR EDR ('safed' dataset)
#### Mars Express
  - HRSC RDRs (support planned)
  - PFS calibrated radiance spectra (support not planned)
  - SPICAM UV and IR EDRs (support planned)
  - MRS most L1A closed loop products: ICL, TCL, TNF, and some ODF products with incomplete labels (support not planned)
  - OMEGA EDR data and geometry cubes
#### Mars Odyssey
  - THEMIS
    - IR RDRs (support planned)
    - v1 VIS/IR geoprojected products (support not planned. v2 are supported. 
      v1 is, per data providers, unsuitable for science due to cosmetic 
      processing)
  - RSS products not listed above as supported (support not planned)
#### MER 1 and 2
  - Terrain MESH and WEDGE products (support not planned)
  - RSS ODFs in mer2rs_0002
#### MESSENGER
  - Ground calibration data for MASCS and NS (support not planned)
#### MGS
  - TES-TSDR PCT (support not planned)
  - TES-TSDR variable-length '.VAR' tables (support not planned)
  - MOLA AEDR and PEDR (support planned)
  - RSS Raw Data products with a "stream" or undefined RECORD_TYPE (support 
    not planned)
  - RSS PostScript files from both Raw Data and Science Data Products (support 
    not planned)
  - MOC Compressed Standard Data Products (*Note: much like the MSL MSSS Camera 
    EDRs discussed below, software for converting these files to uncompressed 
    PDS3-style files exists in the archive.*)
#### MRO
  - RSS .tnf (support not planned)
  - MCS DDRs (support not planned)
  - HiRISE EDR line prefix tables (support planned)
#### MSL
  - Malin Space Science Systems (MSSS) Camera EDRs: "Raw" (EDR) data from the
    Mars Science Laboratory's MSSS-produced cameras (Mastcam, MAHLI, and
    MARDI), are archived in a bespoke compressed format. These images carry
    the extension '.DAT'. Software for converting these files to PDS3-style
    uncompressed raster .IMG files exists in the archive. We plan to either 
    include / compile this code with the installation of this package or (much 
    better) to port `dat2img` to pure Python. Help is welcomed with either of
    these efforts! The MSL "calibrated" (RDR) files for these cameras are not 
    compressed in this way.
  - ChemCam LIBS EDR tables (support not planned)
  - RAD EDRs and RDRs (support planned)
#### New Horizons
  - Pluto encounter derived data: ALICE stellar occultation data
#### Pioneer Venus Orbiter
  - ORPA raw data (support not planned)
  - ORSE ODRs (support not planned)
#### Phoenix
  - TEGA RDRs (support planned)
  - MECA
    - WCL CP/CV-mode RDRs (support not planned)
#### Rosetta
  - Orbiter:
    - CONSERT EDRs, RDRs, and REFDRs (support planned)
    - MIDAS RDRs with .dat file extension (support planned)
    - VIRTIS RDRs (support planned)
    - VIRTIS geometry data
  - Lander:
    - CONSERT EDRs, RDRs, and REFDRs (support planned)
    - SD2 EDRs (support not planned)
#### Ulysses
  - GAS PostScript files (support not planned)
#### Vega 1 and 2
  - PUMA raw and processed data (support not planned)
#### Viking 1 and 2
  - Orbiter
    - IRTM 1989 version (support planned)
    - IRTM 1994 version (support not planned)
#### Voyager 1 and 2
  - ISS ancillary binary tables (support planned; 8-byte VAX_REALs of unknown type)
  - ISS compressed raw images (support not planned)
  - LECP some Jupiter and Saturn SUMM Sector products (support planned; low priority)
  - LECP binary versions of most Uranus products (support not planned)
  - PLS binary versions of VG2-N-PLS-5-RDR-ELEMAGSPHERE-96SEC-V1.0 data (support not planned)
  - PRA Uranus SUMM products (support not planned)
  - RSS ODRs (support not planned)
  - Ring Profile tables with the VAX_REAL data type (support planned; 8-byte 
    VAX_REALs of unknown type)
#### WFF/ATM
  - DEM derived raster images (support planned)
