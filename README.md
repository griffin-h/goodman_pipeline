# Goodman High Throughput Spectrograph
**WARNING** This code is being developed and is not ready for
scientific use. Always check the branch **other than master**.
 
 If you are interested in this software 

The Goodman High Throughput Spectrograph is an imaging spectrograph
 if you wish to know more about the instrument please check the 
 [SOAR website](http://www.ctio.noao.edu/soar/content/goodman-high-throughput-spectrograph)
 
To see full documentation please go to the GitHub hosted site for [Goodman](https://simontorres.github.io/goodman/)

## What is contained in this package?

This repository contains tools for spectroscopy, but after the data is 
reduced, i.e. bias and flat corrected, for that part please use 
[David Sanmartim's](https://github.com/dsanmartim/goodman_ccdreduction) github repository.

#### redspec.py  
 Spectra extraction and wavelength calibration

## How to use it?

Either clone or download this code. To get a list of the possible arguments do:

```shell
/path/to/this/repo/redspec.py --help
```

The simplest way of running this pipeline is to go to your data folder,
already processed with [goodman_ccdreduction](https://github.com/dsanmartim/goodman_ccdreduction)
and execute `redspec.py`


## Important Notes

Needs python2.7 and a newer version of numpy1.12.0 otherwise there will
be problems with numpy.linspace
