# Goodman High Throughput Spectrograph
**WARNING** This is the first release of this pipeline, although we have 
thoroughly tested it there might still be bugs. Please let me know by an
e-mail to storres [at] ctio noao edu.

The Goodman High Throughput Spectrograph is an imaging spectrograph
 if you wish to know more about the instrument please check the 
 [SOAR website](http://www.ctio.noao.edu/soar/content/goodman-high-throughput-spectrograph)
 
To see full documentation please go to the GitHub hosted site for [Goodman](https://simontorres.github.io/goodman/)

## What is contained in this package?

This repository contains tools for spectroscopy, but after the data is 
reduced, i.e. bias and flat corrected, for that part please use 
[David Sanmartim's](https://github.com/dsanmartim/goodman_ccdreduction) github repository.

This package have the following capabilities.

- [x] Identify targets in images
- [x] Trace the target
- [x] Extract the target with background subtraction
- [x] Find the wavelength Solution (Requires User Input)
- [x] Linearize data
- [x] Write wavelength solution to a FITS header
- [x] Create a new file for the wavelength calibrated 1D spectrum

## How to install it?

Either clone or download this code. If you decide to clone it just do ...

Or you can simply go and click _here_ for download a zip file with all the script files.

## How to use it?
 
To get a list of the possible arguments do:

```shell
/path/to/this/repo/redspec.py --help
```

The simplest way of running this pipeline is to go to your data folder,
already processed with [goodman_ccdreduction](https://github.com/dsanmartim/goodman_ccdreduction)
and execute `redspec.py`

```shell
/path/to/this/repo/redspec.py
```

Will run the following defaults:
- [ ] Observing Mode **0**: One solution applied to all night
- [ ] Interactive Mode **True**
- [ ] Data Path **./**
- [ ] Destination folder for processed data **./**
- [ ] Search Pattern **fzh_**
- [ ] Output prefix **g**
- [ ] Reference Files Path [/path/to/this/repo/]**refdata/**
- [ ] Plots Enabled **False**
- [ ] Reference Lamp **None**

## Important Notes

Needs python2.7 and a newer version of numpy1.12.0 otherwise there will
be problems with numpy.linspace

There is a `requirements.txt` file that you can use as follow

```shell
pip2.7 install -r requirements.txt
```
