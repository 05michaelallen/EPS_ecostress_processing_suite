#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 15 07:34:25 2020

@author: mallen
"""


import os
import rasterio as rio
import rasterio.mask
from affine import Affine
import fiona
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import imageio

os.chdir("/Users/mallen/Documents/ecostress_p2/code")


# =============================================================================
# set parameters
# =============================================================================
city = "nyc"

if city == 'la':
    h = 997
    w = 1309
    # shapefile
    with fiona.open("../data/shp/la_county_urban_v1_clean.shp", "r") as shapefile:
        shp = [feature["geometry"] for feature in shapefile] 
elif city == 'nyc':
    h = 667
    w = 626
    with fiona.open("../data/shp/nyc_borough/geo_export_0c79ee67-893d-4acc-b13d-62a73953bedb_utm.shp", "r") as shapefile:
        shp = [feature["geometry"] for feature in shapefile] 

# =============================================================================
# bring in meta
# =============================================================================
# load CSVs
meta = pd.read_csv("../data/" + city + "meta/ecostress_p2_" + city + "_combinedmetadata_v1.csv")
manual = pd.read_csv("../data/" + city + "meta/manualfiltering2.csv")
pxshift = pd.read_csv("../data/" + city + "meta/pxshift_v3.csv")

#concatenate
lam = pd.concat([meta, manual], axis = 1)
#filter
lam = lam[lam['status'] == 1].reset_index()
lams = pd.concat([lam, pxshift['r'], pxshift['c'], pxshift['v']], axis = 1)

lams.to_csv("../data/" + city + "meta/ecostress_p2_" + city + "_combinedmetadata_shift_v1.csv")

# list of filetypes
ftypes = ["lst/ECO2LSTE.",
          "geo/ECO1BGEO.001_Geolocation_view_zenith_",
          "geo/ECO1BGEO.001_Geolocation_view_azimuth_",
          "geo/ECO1BGEO.001_Geolocation_solar_zenith_",
          "geo/ECO1BGEO.001_Geolocation_solar_azimuth_"]
    
# =============================================================================
# loop to nudge and clip
# =============================================================================
offset = 20
for i in range(len(lams)):
    # set row and column shift
    if lams['v'][i] == 0:
        ri = 0
        ci = 0
        indicator = 'N'
    else:
        ri = lams['r'][i]
        ci = lams['c'][i]
        indicator = 'Y'
        
    # now loop through images and shift
    fi = "../data/" + city + "lst/ECO2LSTE." + lams['filename'][i] + "_utm_buffer.tif"
    rf = rio.open(fi)
    rfa = rf.read()
    ti = list(rf.transform) # upper left
    # modify affine based on r/c shift
    ti[2] = ti[2] + offset/2 * ti[0]
    ti[5] = ti[5] - offset/2 * ti[0]
    ti_shift = Affine(ti[0], ti[1], ti[2], ti[3], ti[4], ti[5])
    wi = rf.width - offset
    hi = rf.height - offset
    meta = rf.meta.copy()
    meta.update({'height': hi,
                 'width': wi,
                 'transform': ti_shift})
    
    # shift and write out .tif
    with rio.open("../data/" + city + "lst/ECO2LSTE." + lams['filename'][i] + "_utm_shift.tif", 'w', **meta) as dst:
        # chop off ends based on r/c shift
        rfa_shift = rfa[:, 
                        int(offset/2+ri):int(offset/2+hi+ri), 
                        int(offset/2+ci):int(offset/2+wi+ci)]
        dst.write(rfa_shift)
        
    # clip to shapefile and write to .tif
    for t in range(5):
        if t == 0:
            shifted = rio.open("../data/" + city + ftypes[t] + lams['filename'][i] + "_utm_shift.tif", 'r')
            out_image, out_transform = rio.mask.mask(shifted, shp, crop = True, all_touched = True)
            meta_shifted = shifted.meta.copy()
            meta_shifted.update({"driver": "GTiff",
                                 "height": h, 
                                 "width": w,
                                 "transform": out_transform})
            with rio.open("../data/" + city + ftypes[t] + lams['filename'][i] + "_utm_shift_clip.tif", "w", **meta_shifted) as dest:
                dest.write(out_image)
        else:
            shifted = rio.open("../data/" + city + ftypes[t] + lams['filename'][i][12:] + "_utm.tif", 'r')
            out_image, out_transform = rio.mask.mask(shifted, shp, crop = True, all_touched = True)
            meta_shifted = shifted.meta.copy()
            meta_shifted.update({"driver": "GTiff",
                                 "height": h, 
                                 "width": w,
                                 "transform": out_transform})
            with rio.open("../data/" + city + ftypes[t] + lams['filename'][i][12:] + "_utm_clip.tif", "w", **meta_shifted) as dest:
                dest.write(out_image)