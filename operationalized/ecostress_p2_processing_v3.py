#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Jan 30 08:00:32 2020

@author: allen
"""

import os
import rasterio as rio
from rasterio import mask, crs
from rasterio.warp import calculate_default_transform, reproject, Resampling
import pandas as pd
import numpy as np
import fiona
from datetime import date

# set working directory
os.chdir("/Users/mallen/Documents/ecostress_p2/code/")

# =============================================================================
# functions
# =============================================================================
def reproject_eco(inpath, outpath, new_crs, resolution):
    dst_crs = new_crs
    with rio.open(inpath) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds, 
            resolution = resolution)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rio.open(outpath, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rio.band(src, i),
                    destination=rio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest)

# =============================================================================
# set parameters
# =============================================================================
city = "nyc"

if city == 'la':
    count_cutoff = 1330000
    epsg = 'epsg:26911'
    local_time = 8
elif city == 'nyc':
    count_cutoff = 580000
    epsg = 'epsg:32618' # utm z18n wgs-84
    local_time = 5

# =============================================================================
# filtering to come up with a list of good granules 
# =============================================================================
# first filter based on count
# bring in the QC file from the LST granules
qc = pd.read_csv("../data/" + city + "meta/ECO2LSTE-001-Statistics.csv")
# convert Date to datetime object
qc['Datedt'] = pd.to_datetime(qc["Date"])

# filter for:
# - lst only
# - >1,300,000 filled pixels (i.e. to make sure data are there)
qc_lst = qc[(qc['Dataset'] == "SDS_LST") & 
            (qc['Count'] > count_cutoff)]

# now, pass this list to the cloud image
# the cloud mask is poor (undersamples), so we only use this to filter bad 
# images
# load in the cloud file
cloud = pd.read_csv("../data/" + city + "meta/ECO2CLD-001-SDS-CloudMask-Statistics-QA.csv")
# convert Date to datetime object
cloud['Datedt'] = pd.to_datetime(cloud["Date"])

# filter for the granules we've identified based on orbit number
cloud_filt = cloud[cloud['Datedt'].isin(qc_lst['Datedt'])]

# see if the sizes match (appeears occasionally has different counts of images
# for very large requests)
len(cloud_filt) == len(qc_lst)

# bring back to the qc_lst to grab the filtered granules
import_granules = qc_lst.reset_index()['File Name']

# =============================================================================
# build metadata file
# =============================================================================
# bring in ancillary datasets
geometry = pd.read_csv("../data/" + city + "meta/ECO1BGEO-001-Statistics.csv")
# convert Date to datetime object
geometry['Datedt'] = pd.to_datetime(geometry["Date"])
geometry_filt = geometry[geometry['Datedt'].isin(qc_lst['Datedt'])]

# split into different variables
# take only the mean
view_zenith = geometry_filt[geometry_filt["Dataset"] == "Geolocation_view_zenith"][['Mean']].reset_index(drop=True)
solar_zenith = geometry_filt[geometry_filt["Dataset"] == "Geolocation_solar_zenith"][['Mean']].reset_index(drop=True)
view_azimuth = geometry_filt[geometry_filt["Dataset"] == "Geolocation_view_azimuth"][['Mean']].reset_index(drop=True)
solar_azimuth = geometry_filt[geometry_filt["Dataset"] == "Geolocation_solar_azimuth"][['Mean']].reset_index(drop=True)

# concat them into a dataframe
metadata = pd.concat([import_granules.str[9:45], view_zenith, solar_zenith, view_azimuth, solar_azimuth], axis = 1)
metadata.columns = ["filename", 'view_zenith', 'solar_zenith', 'view_azimuth', 'solar_azimuth']

# tack on extra columns that arent needed as series
metadata['meanlst'] = qc_lst['Mean'].reset_index(drop=True)

# tack on hour, day, month, doy, and time (utc)
metadata['year'] = import_granules.str[24:28].astype(int)
metadata['doy'] = import_granules.str[28:31].astype(int)
metadata['hour'] = import_granules.str[31:33].astype(int)
metadata['minute'] = import_granules.str[33:35].astype(int)
metadata['datetime'] = qc_lst.reset_index()['Datedt']
metadata['month'] = pd.DatetimeIndex(metadata['datetime']).month
metadata['day'] = pd.DatetimeIndex(metadata['datetime']).day

# create seasons
y = 2000 # dummy leap year to allow input X-02-29 (leap day)
s = []
for i in range(len(metadata)):
    di = metadata['datetime'].iloc[i]
    di = di.replace(year = y)
    if di < date(y, 3, 20):
        s.append('winter')
    elif di >= date(y, 3, 20) and di < date(y, 6, 21):
        s.append('spring')
    elif di >= date(y, 6, 21) and di < date(y, 9, 22):
        s.append('summer')
    elif di >= date(y, 9, 22) and di < date(y, 12, 21):
        s.append('fall')
    else:
        s.append('winter')
metadata['season'] = pd.Series(s)

# create column for PST
metadata['hourpst'] = metadata.hour
for i in range(0, len(metadata)):
    if metadata['hourpst'].iloc[i] < local_time:
        metadata['hourpst'].iloc[i] = metadata['hourpst'].iloc[i] + 24 - local_time
        metadata['doy'].iloc[i] = metadata['doy'].iloc[i] - 1
    else:
        metadata['hourpst'].iloc[i] = metadata['hourpst'].iloc[i] - local_time

# create hourfrac column
metadata['hourfrac'] = metadata['hourpst'] + metadata['minute']/60

# output metadata as a csv
metadata.to_csv("../data/" + city + "meta/ecostress_p2_" + city + "_combinedmetadata_v1.csv")

# =============================================================================
# import images using the filtered list of granules
# =============================================================================
# set the target resolution
resolution = [70, 70]

# list of filetypes
ftypes = ["lst/ECO2LSTE.",
          "geo/ECO1BGEO.001_Geolocation_view_zenith_",
          "geo/ECO1BGEO.001_Geolocation_view_azimuth_",
          "geo/ECO1BGEO.001_Geolocation_solar_zenith_",
          "geo/ECO1BGEO.001_Geolocation_solar_azimuth_"]

# reproject using the reproject_eco function above
# reprojects to utm zone 11 north with 70m spatial resolution
# method = nn
for i in range(len(import_granules)):
    for t in range(5):
        if t == 0:
            granulei = import_granules.iloc[i][9:]
            reproject_eco(inpath = "../data/" + city + ftypes[t] + granulei + ".tif",
                          outpath = "../data/"  + city + ftypes[t] + granulei + "_utm.tif", 
                          new_crs = epsg,
                          resolution = resolution)
        else:
            granulei = import_granules.iloc[i][21:]
            reproject_eco(inpath = "../data/" + city + ftypes[t] + granulei + ".tif",
                          outpath = "../data/"  + city + ftypes[t] + granulei + "_utm.tif", 
                          new_crs = epsg,
                          resolution = resolution)