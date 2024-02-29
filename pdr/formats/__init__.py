"""This module contains special case formats for nonconforming or malformatted data
types organized by mission and/or instrument. The `checkers` module consists of functions
that are called by `pdr.func.specialize` to determine if a given file meets the stated criteria.
If a file meets the criteria in the checker, a file from the respective special case formats
module is returned. If not, the base pdr workflow is continued."""

from .checkers import *
import pdr.formats.cassini as cassini
import pdr.formats.clementine as clementine
import pdr.formats.dawn as dawn
import pdr.formats.diviner as diviner
import pdr.formats.epoxi as epoxi
import pdr.formats.galileo as galileo
import pdr.formats.ihw as ihw
import pdr.formats.juno as juno
import pdr.formats.lroc as lroc
import pdr.formats.lro as lro
import pdr.formats.mariner as mariner
import pdr.formats.mer as mer
import pdr.formats.mex as mex
import pdr.formats.mgn as mgn
import pdr.formats.mgs as mgs
import pdr.formats.mro as mro
import pdr.formats.msl_apxs as msl_apxs
import pdr.formats.msl_cmn as msl_cmn
import pdr.formats.msl_ccam as msl_ccam
import pdr.formats.msl_places as msl_places
import pdr.formats.nh as nh
import pdr.formats.odyssey as odyssey
import pdr.formats.pvo as pvo
import pdr.formats.rosetta as rosetta
import pdr.formats.saturn_rpx as saturn_rpx
import pdr.formats.themis as themis
import pdr.formats.ulysses as ulysses
import pdr.formats.vega as vega
import pdr.formats.viking as viking
import pdr.formats.voyager as voyager
