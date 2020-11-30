#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed Nov 18 09:04:21 2020

@author: mallen
"""


# Import packages 
import requests as r
import getpass, pprint, time, os, cgi, json
import geopandas as gpd

# Set input directory, change working directory
indir = "/Users/mallen/Documents/ecostress_p2/code"
os.chdir(indir)
api = 'https://lpdaacsvc.cr.usgs.gov/appeears/api/'

# input username and password
user = getpass.getpass(prompt = 'Enter NASA Earthdata Login Username: ')
password = getpass.getpass(prompt = 'Enter NASA Earthdata Login Password: ')

# Insert API URL, call login service, provide credentials & return json
token_response = r.post('{}login'.format(api), auth=(user, password)).json()
del user, password
token_response

# list all products
product_response = r.get('{}product'.format(api)).json()
# Create a dictionary indexed by product name & version
products = {p['ProductAndVersion']: p for p in product_response}
# print for ecostress lst
products['ECO2LSTE.001']

# create a list of the request
prods = ['ECO2LSTE.001']
prods.append('ECO1BGEO.001')
prods.append('ECO2CLD.001')

# list layers from products
#r.get('{}product/{}'.format(api, prods[2])).json()

# create list of layers
layers = [#(prods[0],'SDS_LST'),
          #(prods[0],'SDS_QC')
          (prods[1],'Geolocation_view_zenith'),
          (prods[1],'Geolocation_view_azimuth'),
          (prods[1],'Geolocation_solar_zenith'),
          (prods[1],'Geolocation_solar_azimuth'),
          #(prods[2],'SDS_CloudMask')
          ]

# convert tupled list of layers to list of dict
prodLayer = []
for l in layers:
    prodLayer.append({
            "layer": l[1],
            "product": l[0]
          })

# =============================================================================
# 
# =============================================================================
# save token
token = token_response['token']
head = {'Authorization': 'Bearer {}'.format(token)}

# import the request shapefile
#nps = gpd.read_file('/Users/mallen/Documents/ecostress_p2/data/shp/nyc_appeears_request.shp').to_json()
nps = gpd.read_file('../data/shp/la_appeears_request.shp').to_json()
# convert to json
nps = json.loads(nps)

# name the task
task_name = 'la_geo_nov'
# select task type, projection, and output
task_type = 'area'
proj = 'geographic'
outFormat = 'geotiff'
# start and end date
startDate = '07-01-2018'
#startDate = '10-15-2020'
endDate = '11-30-2020'
recurring = False

# compile into an area request
task = {
    'task_type': task_type,
    'task_name': task_name,
    'params': {
         'dates': [
         {
             'startDate': startDate,
             'endDate': endDate
         }],
         'layers': prodLayer,
         'output': {
                 'format': {
                         'type': outFormat}, 
                         'projection': proj},
         'geo': nps,
    }
}

# submit
task_response = r.post('{}task'.format(api), json=task, headers=head).json()
task_response
