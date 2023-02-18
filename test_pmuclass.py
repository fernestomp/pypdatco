# -*- coding: utf-8 -*-
'''
script to test PMU class
'''
from class_PMU import PMU
import matplotlib.pyplot as plt
import pandas as pd
from pandas.plotting import register_matplotlib_converters
register_matplotlib_converters()
from drawnow import drawnow

#print dataframe dict
p = PMU("10.10.200.22")
p.connect()
d = p.read_dataframe_dict()
p.disconnect()
for keys,values in d.items():
    print(' {}: {}'.format( keys,values))

########################################################
# matplotlib
####################################################
#to plot continously
def make_fig():
    plt.xticks(rotation=70)
    plt.tight_layout()
    plt.plot(x, y)

plt.ion()  # enable interactivity
fig = plt.figure()  # make a figure
plt.autoscale(enable=True)
x = list()
y = list()

p = PMU("10.10.200.22")
p.connect()
#read  measurements
#this code is not optimal, n frames per second are expected
#is only for testing purposes, data could be lost or superimposed
n= 0
dataframenumber = 0 #counter for dataframes
#ask for n dataframes
for i in range(100):
    d = p.read_dataframe_dict()
    x.append(pd.to_datetime(d['TIME'], format = '%Y-%m-%d %H:%M:%S.%f'))
    y.append(d['FREQ'])  # or any arbitrary update to your figure's data
    drawnow(make_fig)
    if len(x) >30:
        x.pop(0)
        y.pop(0)

p.disconnect()
