#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Oct 15 07:34:25 2020

@author: mallen
"""


import os
import rasterio as rio
import rasterio.mask
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import colorcet
import scipy as sp
import fiona
from skimage.morphology import closing
import cartopy.crs as ccrs

os.chdir("/Users/mallen/Documents/ecostress_p2/code")

# =============================================================================
# functions
# =============================================================================
### normalize
def norm(array):
    n = 2 * (array - np.nanmin(array))/(np.nanmax(array) - np.nanmin(array)) - 1
    return n

# =============================================================================
# set parameters
# =============================================================================
city = "nyc"
px = 70
if city == 'la':
    bi = 720
    bj = 360
    w = 90
    h = 200
    z = 11
    
elif city == 'nyc':
    bi = 490
    bj = 160
    w = 70
    h = 70
    z = 18

# =============================================================================
# bring in meta
# =============================================================================
lameta = pd.read_csv("../data/" + city + "meta/ecostress_p2_" + city + "_combinedmetadata_v1.csv")
lamanual = pd.read_csv("../data/" + city + "meta/manualfiltering2.csv")

#concat
lam = pd.concat([lameta, lamanual], axis = 1)
#filter
lam = lam[lam['status'] == 1].reset_index()

# buffer shapefile
shp = fiona.open("../data/shp/" + city + "_buffer.shp", "r")
shp = [feature["geometry"] for feature in shp] 

# =============================================================================
# harmonize multiple sets
# =============================================================================
for b in range(len(lam)):
    br = rio.open("../data/" + city + "lst/ECO2LSTE." + lam['filename'][b] + "_utm.tif")
    brm, brmt = rio.mask.mask(br, shp, all_touched = True, crop = True)
    brmeta = br.meta
    brmeta.update({'height': brm.shape[1],
                   'width': brm.shape[2],
                   'transform': brmt})
    with rio.open("../data/" + city + "lst/ECO2LSTE." + lam['filename'][b] + "_utm_buffer.tif", 'w', **brmeta) as dst:
        dst.write(brm)

# =============================================================================
# nudging routine 
# =============================================================================
### reference image
if city == 'la':
    fr = "../data/" + city + "lst/ECO2LSTE.001_SDS_LST_doy2020036034759_aid0001_utm_buffer.tif"
elif city == 'nyc':
    fr = "../data/" + city + "lst/ECO2LSTE.001_SDS_LST_doy2020165144025_aid0001_utm_buffer.tif"
frr = rio.open(fr).read()[0,:,:].astype(float) * 0.02
frr[(frr < 250) | (frr > 340)] = np.nan # filter

# sub of reference
frrs = frr[bi:bi+h, bj:bj+w]
p = plt.imshow(frrs)
plt.colorbar(p)

# normalize reference, square to boost signal
frrs0 = frrs.copy() 
frrs0m = (np.max(frrs0) - np.min(frrs0))/2 + np.min(frrs0)
# now corsen radiometric to two regions
frrs0[frrs0 <= frrs0m] = 0
frrs0[frrs0 > frrs0m] = 1
# fill holes
frrs0 = sp.ndimage.morphology.binary_closing(frrs0).astype(int)

# =============================================================================
# loop nudging the gradient around over the reference gradient
# =============================================================================
# parameters for plot
proj = ccrs.UTM(z, southern_hemisphere = False)
roct = rio.open(fr).bounds

# create bbox
bbox = [roct[0] + bj*px, roct[0] + bj*px + px*w, 
        roct[3] - bi*px - px*h, roct[3] - bi*px]

r = []
c = []
v = []
for f in range(len(lam)):
    if lam['status'][f] != 1:
        r.append(-999)
        c.append(-999)
    else:
        ### test image 
        ft = "../data/" + city + "lst/ECO2LSTE." + lam['filename'][f] + "_utm_buffer.tif"
        ftt = rio.open(ft).read()[0,:,:].astype(float) * 0.02
        ftt[(ftt < 263) | (ftt > 340)] = np.nan # filter
        
        d0 = np.zeros([20, 20])
        for i in range(0, 20):
            for j in range(0, 20):
                # center the row/column offset
                rij = i - 10
                cij = j - 10
                # cut test
                ftts = ftt[bi+rij:bi+h+rij, bj+cij:bj+w+cij]
                # normalize to -1 to 1
                ftts0 = ftts.copy() #np.absolute(norm(ftts))
                ftts0m = (np.max(ftts0) - np.min(ftts0))/2 + np.min(ftts0)
                ### subloop to flip the sea/land gradient if during the day
                # sample sea and land
                if city == 'la':
                    land = np.mean(ftts0[0:10, 65:75])
                    sea = np.mean(ftts0[100:110, 0:10])
                elif city == 'nyc':
                    sea = np.mean(ftts0[0:10, 0:10])
                    land = np.mean(ftts0[60:70, 60:70])
                if land > sea:
                    # this is the opposite of the reference, so we flit the temps
                    # make temps negative
                    ftts0 = -ftts0.copy()
                    # make binary
                    ftts0[ftts0 > -ftts0m] = 1
                    ftts0[ftts0 <= -ftts0m] = 0
                    # fill holes
                    ftts0 = sp.ndimage.morphology.binary_closing(ftts0).astype(int)
                    # create in column/i direction
                    d0[i, j] = np.nansum(np.absolute(ftts0 - frrs0))
                else:
                    # make binary
                    ftts0[ftts0 <= ftts0m] = 0
                    ftts0[ftts0 > ftts0m] = 1
                    # fill holes
                    ftts0 = sp.ndimage.morphology.binary_closing(ftts0).astype(int)
                    # create in column/i direction
                    d0[i, j] = np.nansum(np.absolute(ftts0 - frrs0))
                
        # find minimum 
        rf, cf = np.where(np.absolute(d0) == np.absolute(d0).min())
        rf = int(rf[0]) - 9
        cf = int(cf[0]) - 9
        r.append(rf) # in the case of multiples, take first solution
        c.append(cf) # 9 to account for base 0
        
        ### plot diagnostic
        fig, [ax1, ax2] = plt.subplots(1, 2, subplot_kw = dict(projection = proj))
        ### OG image
        ax1.set_extent(bbox, proj)
        ax1.coastlines(resolution = '10m', 
                       color = "black",
                       linewidth = 1.5,
                       zorder = 10)

        og = ftt[bi:bi+h, bj:bj+w]
        chi = ax1.imshow(og,
                         extent = bbox, 
                         origin = 'upper',
                         cmap = colorcet.cm.CET_L8)
        #ax1.set_xticks([370000])
        #ax1.set_yticks([3740000, 3745000, 3750000])
        
        ### shifted
        ax2.set_extent(bbox, proj)
        ax2.coastlines(resolution = '10m', 
                       color = "black",
                       linewidth = 1.5,
                       zorder = 10)
        shifted = ftt[bi+rf:bi+h+rf, bj+cf:bj+w+cf]
        egg = ax2.imshow(shifted,
                         extent = bbox, 
                         origin = 'upper',
                         cmap = colorcet.cm.CET_L8)
        #ax2.set_xticks([370000])
        #ax2.set_yticks([3740000, 3745000, 3750000])
        
        ax1.tick_params(top = True, right = True, direction = 'out', zorder = 8)
        ax2.tick_params(top = True, right = True, direction = 'out', zorder = 8)
        # add labels
        ax2.text(0.03, 
                 0.03, 
                 "after \nfn: " + lam['filename'][f][12:28] + "\nrow shift: " + str(rf) + "\ncol shift: " + str(cf), 
                 c = '1',
                 va = 'bottom', 
                 ha = 'left', 
                 zorder = 500,
                 transform = ax2.transAxes)
        plt.show()
        
        ### user input to sort good from bad
        v.append(int(input("1 for improved, 0 for made worse: ")))

# concat with df
pxshift = pd.concat([lam['filename'], pd.Series(r, name = 'r'), pd.Series(c, name = 'c'), pd.Series(v, name = 'v')], axis = 1)
pxshift.to_csv("../data/" + city + "meta/pxshift_v3.csv")

