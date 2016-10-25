from astropy.io import fits
import numpy as np
import matplotlib.pyplot as plt
from astropy.modeling import models, fitting
from astropy.stats import sigma_clip
from specutils.wcs import specwcs
import scipy.interpolate
from linelist import ReferenceData
import logging as log
import glob  # remove later
import sys
import time
import wsBuilder

FORMAT = '%(levelname)s:%(filename)s:%(module)s: 	%(message)s'
log.basicConfig(level=log.DEBUG, format=FORMAT)


class WavelengthCalibration:
    def __init__(self, path, sci_pack, science_object, args):
        self.args = args
        self.wsolution = None
        self.reference_data = ReferenceData()
        self.science_object = science_object
        self.slit_offset = 0
        self.interpolation_size = 200
        self.line_search_method = 'derivative'
        """Instrument configuration and spectral characteristics"""
        self.gratings_dict = {'SYZY_400': 400, 'KOSI_600': 600, '930': 930, 'RALC_1200-BLUE': 1200}
        self.grating_frequency = 0
        self.grating_angle = float(0)
        self.camera_angle = float(0)
        self.binning = 1
        self.pixel_count = 0
        self.alpha = 0
        self.beta = 0
        self.center_wavelength = 0
        self.blue_limit = 0
        self.red_limit = 0
        """Interactive wavelength finding"""
        self.reference_clicks_x = []
        self.reference_clicks_y = []
        self.raw_data_clicks_x = []
        self.raw_data_clicks_y = []
        self.click_input_enabled = True
        self.reference_bb = None
        self.raw_data_bb = None
        self.i_fig = None
        self.ax1 = None
        self.ax2 = None
        self.points_ref = None
        self.points_raw = None
        self.line_raw = None
        self.filling_value = 1000
        self.events = True
        self.first = True
        self.evaluation_comment = None
        # self.binning = self.header0[]
        """Remove this one later"""
        self.pixelcenter = []
        """End Remove"""
        """this data must come parsed"""
        self.path = path
        self.all_data = sci_pack[0]
        self.all_headers = sci_pack[1]
        self.sci = self.all_data[0]
        self.header = self.all_headers[0]
        self.sci_filename = self.science_object.file_name
        self.history_of_lamps_solutions = {}
        self.reference_solution = None

    def __call__(self, wsolution_obj=None):
        log.info('Processing Science Target: %s' % self.header['OBJECT'])
        if wsolution_obj is None:
            if self.science_object.lamp_count > 0:
                for l in range(1, self.science_object.lamp_count + 1):
                    self.calibration_lamp = self.science_object.lamp_file[l - 1]
                    self.data0 = self.all_data[l]
                    self.raw_pixel_axis = range(1, len(self.data0) + 1, 1)
                    self.header0 = self.all_headers[l]
                    self.lamp_name = self.header0['OBJECT']
                    log.info('Processing Comparison Lamp: %s' % self.lamp_name)
                    self.data1 = self.interpolate(self.data0)
                    self.lines_limits = self.get_line_limits()
                    self.lines_center = self.get_line_centers(self.lines_limits)
                    self.spectral = self.get_spectral_characteristics()
                    if self.args.interactive_ws:

                        self.interactive_wavelength_solution()
                        if self.wsolution is not None:
                            self.linear_lamp = self.linearize_spectrum(self.data0)
                            self.header0 = self.add_wavelength_solution(self.header0,
                                                                        self.linear_lamp,
                                                                        self.science_object.lamp_file[l - 1])
                        else:
                            log.error('It was not possible to get a wavelength solution from this lamp.')
                            return
                    else:
                        log.warning('Automatic Wavelength Solution is not fully implemented yet')
                        self.automatic_wavelength_solution()
                        # self.wsolution = self.wavelength_solution()
                self.linearized_sci = self.linearize_spectrum(self.sci)
                self.header = self.add_wavelength_solution(self.header, self.linearized_sci, self.sci_filename)
                wavelength_solution = WavelengthSolution(solution_type='non_linear',
                                                         model_name='chebyshev',
                                                         model_order=3,
                                                         model=self.wsolution,
                                                         ref_lamp=self.calibration_lamp,
                                                         eval_comment=self.evaluation_comment)
                return wavelength_solution
            else:
                log.error('There are no lamps to process')
        else:
            self.wsolution = wsolution_obj.wsolution
            self.calibration_lamp = wsolution_obj.reference_lamp
            self.evaluation_comment = wsolution_obj.evaluation_comment
            print 'wavelengthSolution ', self.wsolution
            self.linearized_sci = self.linearize_spectrum(self.sci)
            self.header = self.add_wavelength_solution(self.header,
                                                       self.linearized_sci,
                                                       self.sci_filename,
                                                       self.evaluation_comment)

    def get_wsolution(self):
        """Get the mathematical model of the wavelength solution

        The wavelength solution is a callable mathematical function from astropy.modeling.models
        By obtaining this solution it can be applied to a pixel axis.

        Returns:
            wsolution (callable): A callable mathematical function

        """
        if self.wsolution is not None:
            return self.wsolution
        else:
            log.error("Wavelength Solution doesn't exist!")
            return None

    def get_calibration_lamp(self):
        """Get the name of the calibration lamp used for obtain the solution

        The filename of the lamp used to obtain must go to the header for documentation

        Returns:
            calibration_lamp (str): Filename of calibration lamp used to obtain wavelength solution

        """
        if self.wsolution is not None and self.calibration_lamp is not None:
            return self.calibration_lamp
        else:
            log.error('Wavelength solution has not been calculated yet.')

    def interpolate(self, spectrum):
        """Creates an interpolated version of the input spectrum

        This method creates an interpolated version of the input array, it is used mainly for a spectrum but it can
        also be used with any unidimensional array, assuming you are happy with the interpolation_size attribute
        defined for this class. The reason for doing interpolation is that it allows to find the lines and its
        respective center more precisely. The default interpolation size is 200 (two hundred) points.

        Args:
            spectrum (array): an uncalibrated spectrum or any unidimensional array.

        Returns:
            Two dimensional array containing x-axis and interpolated array. The x-axis preserves original pixel values.

        """
        x_axis = range(1, spectrum.size + 1)
        x0 = x_axis[0]
        x1 = x_axis[-1]
        new_x_axis = np.linspace(x0, x1, spectrum.size * self.interpolation_size)

        tck = scipy.interpolate.splrep(x_axis, spectrum, s=0)
        new_spectrum = scipy.interpolate.splev(new_x_axis, tck, der=0)
        return [new_x_axis, new_spectrum]

    @staticmethod
    def recenter_line_by_model(x, y, max_val, max_pos, model='gauss'):
        """Recalculates the center of a line by fitting a model

        This method fits one of the three line profiles to the input data. It works well in lines with good signal to
        noise ratios and with little contaminants (please see Notes). This method will be most likely removed since
        the combination of the line detection method plus the interpolation of the spectrum gives a very good result.

        Notes:
            This method was kept for development purposes. According to the test performed the line centers that were
            fed to this method were always better than the output since the fits were confused by contaminants.

        Args:
            x (array): x-axis of data in pixel values.
            y (array): the data to be fitted. A section around an spectral line.
            max_val (float): Value at line's peak.
            max_pos (int): Index of line's peak.
            model (str): Name of the line profile to be fitted. One of this three: "gauss", "lorentz" or "voigt".

        Returns:
            new_center (float): Value of the re-calculated center of the line.

        """
        if x.size == y.size:
            if model == 'gauss':
                gauss_init = models.Gaussian1D(amplitude=max_val, mean=max_pos, stddev=4)
                fit_gaussian = fitting.LevMarLSQFitter()
                gauss = fit_gaussian(gauss_init, x, y)
                fitted_model = gauss
                new_center = gauss.mean.value
                return new_center
            elif model == 'lorentz':
                lorentz_init = models.Lorentz1D(amplitude=max_val, x_0=max_pos, fwhm=8)
                # log.debug('Amplitude: %s X_0: %s FWHM: %s', max_val, max_pos, 8)
                fit_lorentz = fitting.LevMarLSQFitter()
                lorentz = fit_lorentz(lorentz_init, x, y)
                # print(lorentz)
                fitted_model = lorentz
                new_center = lorentz.x_0.value
                return new_center
            elif model == 'voigt':
                voigt_init = models.Voigt1D(x_0=max_pos, amplitude_L=max_val, fwhm_L=8, fwhm_G=8)
                fit_voigt = fitting.LevMarLSQFitter()
                voigt = fit_voigt(voigt_init, x, y)
                # print(voigt)
                fitted_model = voigt
                new_center = voigt.x_0.value
                return new_center
            else:
                log.error('Unknown model %s', model)
                return False
            # return new_center
            #return new_center
        else:
            return False

    def get_line_limits(self):
        """Method for identifying lines in a spectrum

        This is the spectral line identifying method. It calculates a pseudo-derivative of the spectrum thus determining
        peaks. For a typical spectrum a pseudo-derivative, from now on just "derivative", will produce a series of
        positive and negative peaks, for emission lines. Since we will be using it for comparison lamps only we don't
        have to worry about absorption lines and therefore this method only detects emission lines.
        A threshold is defined by calculating the 75 percent of the standard deviation of the derivative. There
        is no particular reason for choosing 75 percent is just the value that worked best for all the test subjects.
        Then any search for lines must be done for values above and below of the threshold and its negative
        respectively.  There are a few control mechanisms that ensures that an actual good line is being detected. For
        instance: For each line both positive and negative derivative's peaks are stored and are called limits. In order
        to add a (first) positive limits the number of previously stored limits must be even, meaning that we are
        "opening" a new line. Correspondingly if we are adding  a (last) negative limit we have to have added previously
        a odd amount of limits meaning that we are "closing" a line. At this point there is another constraint, it
        cannot be separated by an amount larger than a defined spacing, or we would be having a very broad line and lamp
        lines are expected to be very narrow.

        Notes:
            The lines detected by this method are usually the best lines in the spectrum. There is a certain amount of
            lines missed but in very crowded regions.

            Very important to note that the line centers found using the data produced here are very precise.

        Returns:
            limits (list): List of line limits in consecutive pairs. This is considered by the method that uses this
            list for further processing. The values are index values not pixel values.

        """
        """
        pixel_axis = self.data1[0]
        if self.line_search_method == 'threshold':
            median_value = np.median(self.data1[1])
            mean_value = np.mean(self.data1[1])
            threshold = median_value + mean_value
            keep_searching = True
            features = []
            while keep_searching:
                feature = []
                subx = []
                for i in range(len(self.data1[1])):
                    if self.data1[1][i] > threshold:
                        feature.append(self.data1[1][i])
                        subx.append(pixel_axis[i])
                    elif feature != [] and len(feature) >= 3:
                        features.append([subx, feature])
                        # print(len(feature))
                        feature = []
                        subx = []
                    else:
                        feature = []
                        subx = []
                    if i == len(self.data1[1]) - 1:
                        keep_searching = False
            print(len(features))
            return False
        """
        if self.line_search_method == 'derivative':
            """in fact is a pseudo-derivative"""
            derivative = []
            # derivative2 = []
            faux_x = range(0, len(self.data1[1]) - 1)
            # faux_x2 = range(0, len(self.data1[1]) - 2)
            # print faux_x
            for i in faux_x:
                derivative.append(self.data1[1][i + 1] - self.data1[1][i])
            # for e in faux_x2:
            #    derivative2.append(derivative[e] - derivative[e+1])
            threshold = np.std(derivative) * .75
            new_range = 0
            spacing = 1500
            limits = []
            for i in range(len(derivative) - 1):
                if i > new_range:
                    if derivative[i] > threshold and derivative[i + 1] - derivative[i] >= 0:
                        partial_max = i + np.argmax(derivative[i:i + spacing])
                        # print i, partial_min
                        new_range = partial_max + (partial_max - i)
                        if limits == [] or len(limits) % 2 == 0:
                            limits.append(partial_max)
                        else:
                            plt.axvline(partial_max, color='k')
                    elif derivative[i] < -threshold and derivative[i + 1] - derivative[i] <= 0:
                        partial_min = i + np.argmin(derivative[i:i + spacing])
                        new_range = partial_min + (partial_min - i)
                        if len(limits) % 2 == 1 and partial_min - limits[-1] < spacing:
                            limits.append(partial_min)
                            # plt.axvline(partial_max, color='g')
                        elif limits != []:
                            if partial_min - limits[-1] > spacing:
                                plt.axvline(partial_min, color='m')
                                limits = limits[:-1]
            if len(limits) % 2 == 1:
                limits = limits[:-1]
            """
            # Produce Plots
            for i in range(len(limits)):
                if i % 2 == 0:
                    plt.axvline(limits[i], color='r')
                elif i % 2 == 1:
                    plt.axvline(limits[i], color='g')

            plt.title('Line Identification')
            # plt.plot(self.data1[1], label='Spectrum')
            plt.plot(faux_x, derivative, label='1st Derivative')
            plt.axhline(0, color='m')
            # plt.plot(faux_x2, derivative2, label='2nd')
            plt.axhline(threshold)
            plt.axhline(-threshold)
            plt.legend(loc='best')
            # plt.plot(pixel_axis, self.data1[1])
            plt.savefig(self.path + 'line-identification-201.png', dpi=300)
            plt.show()
            # """
            return limits

    def get_line_centers(self, limits):
        """Finds the center of the lines using limits previously found

        This method is very simple and could be integrated in the get_line_limits method but I'd rather have the limit
        information available for later. Basically finds the mean value of the line limits and then finds the
        correspoing pixel value, adds it up to the "centers" list.

        Args:
            limits (list): Line limits in the list's index domain.

        Returns:
            centers (list): Line centers in pixel values as floats.

        """
        centers = []
        for i in range(0, len(limits), 2):
            center = (limits[i] + limits[i + 1]) / 2.
            width = limits[i + 1] - limits[i]
            pixel_width = self.data1[0][limits[i + 1]] - self.data1[0][limits[i]]
            log.debug('Approximate FWHM: %s pix %s Angstrom (pix * 0.65)', pixel_width, pixel_width * 0.65)
            i_min = int(center - 2 * width)
            i_max = int(center + 2 * width)
            pixel_axis = self.data1[0][i_min:i_max]
            data_axis = self.data1[1][i_min:i_max]
            pixel_center = self.data1[0][int(round(center))]
            center_val = self.data1[1][int(round(center))]
            new_center = self.recenter_line_by_model(pixel_axis, data_axis, center_val, pixel_center, 'gauss')
            """
            plt.plot(pixel_axis, data_axis)
            plt.axvline(pixel_center)
            plt.axvline(new_center, color='m')
            plt.show()
            """
            self.pixelcenter.append([pixel_center, center_val])
            centers.append(pixel_center)
            # print(center, width)
        return centers

    def get_spectral_characteristics(self):
        """Calculates some Goodman's specific spectroscopic values.

        From the Header value for Grating, Grating Angle and Camera Angle it is possible to estimate what are the limits
        wavelength values and central wavelength. It was necessary to add offsets though, since the formulas provided
        are slightly off. The values are only an estimate.

        Returns:
            spectral_characteristics (dict): Contains the following parameters:
                                            center: Center Wavelength
                                            blue: Blue limit in Angstrom
                                            red: Red limit in Angstrom
                                            alpha: Angle
                                            beta: Angle
                                            pix1: Pixel One
                                            pix2: Pixel Two

        """
        blue_correction_factor = -90
        red_correction_factor = -60
        self.grating_frequency = self.gratings_dict[self.header0['GRATING']]
        self.grating_angle = float(self.header0['GRT_ANG'])
        self.camera_angle = float(self.header0['CAM_ANG'])
        # binning = self.header0[]
        # TODO GET BINNING FROM THE RIGHT SOURCE
        self.binning = 1
        # self.pixel_count = len(self.data0)
        """Calculations"""
        self.alpha = self.grating_angle + self.slit_offset
        self.beta = self.camera_angle - self.grating_angle
        self.center_wavelength = 10 * (1e6 / self.grating_frequency) * (
            np.sin(self.alpha * np.pi / 180.) + np.sin(self.beta * np.pi / 180.))
        self.blue_limit = 10 * (1e6 / self.grating_frequency) * (
            np.sin(self.alpha * np.pi / 180.) + np.sin((self.beta - 4.656) * np.pi / 180.)) + blue_correction_factor
        self.red_limit = 10 * (1e6 / self.grating_frequency) * (
            np.sin(self.alpha * np.pi / 180.) + np.sin((self.beta + 4.656) * np.pi / 180.)) + red_correction_factor
        pixel_one = self.predicted_wavelength(1)
        pixel_two = self.predicted_wavelength(2)
        log.debug('Center Wavelength : %s Blue Limit : %s Red Limit : %s',
                  self.center_wavelength,
                  self.blue_limit,
                  self.red_limit)
        spectral_characteristics = {'center': self.center_wavelength,
                                    'blue': self.blue_limit,
                                    'red': self.red_limit,
                                    'alpha': self.alpha,
                                    'beta': self.beta,
                                    'pix1': pixel_one,
                                    'pix2': pixel_two}
        return spectral_characteristics

    def predicted_wavelength(self, pixel):
        a = self.alpha
        b = self.beta
        # c = self.pixel_count
        d = self.binning
        e = self.grating_frequency
        wavelength = 10 * (1e6 / e) * (np.sin(a * np.pi / 180.) +
                                       np.sin((b * np.pi / 180.) +
                                              np.arctan((pixel * d - 2048) * 0.015 / 377.2)))
        return wavelength

    def find_more_lines(self):
        """Method to add more lines given that a wavelength solution already exists

        This method is part of the interactive wavelength solution mechanism. If a wavelength solution exist it uses the
        line centers in pixels to estimate their respective wavelength and then search for the closest value in the list
        of reference lines for the elements in the comparison lamp. Then it filters the worst of them by doing sigma
        clipping. Finally it adds them to the class' variables that contains the list of reference points.

        Better results are obtained if the solution is already good. Visual inspection also improves final result.
        """
        new_physical = []
        new_wavelength = []
        square_differences = []
        if self.wsolution is not None:
            wlines = self.wsolution(self.lines_center)
            for i in range(len(wlines)):
                closer_index = np.argmin(abs(self.reference_data.get_line_list_by_name(self.lamp_name) - wlines[i]))
                rline = self.reference_data.get_line_list_by_name(self.lamp_name)[closer_index]
                rw_difference = wlines[i] - rline
                print 'Difference w - r ', rw_difference, rline
                square_differences.append(rw_difference ** 2)
                new_physical.append(self.lines_center[i])
                new_wavelength.append(rline)
            clipped_differences = sigma_clip(square_differences, sigma=2, iters=10)
            if len(new_wavelength) == len(new_physical) == len(clipped_differences):
                for e in range(len(new_wavelength)):
                    if clipped_differences is not np.ma.masked and new_wavelength[e] not in self.reference_clicks_x:
                        self.reference_clicks_x.append(new_wavelength[e])
                        self.reference_clicks_y.append(self.filling_value)
                        self.raw_data_clicks_x.append(new_physical[e])
                        self.raw_data_clicks_y.append(self.filling_value)
        return True

    def interactive_wavelength_solution(self):
        """Find the wavelength solution interactively



        """
        reference_file = self.reference_data.get_reference_lamps_by_name(self.lamp_name)
        if reference_file is not None:
            log.info('Using reference file: %s', reference_file)
            reference_plots_enabled = True
            ref_data = fits.getdata(reference_file)
            ref_header = fits.getheader(reference_file)
            fits_ws_reader = wsBuilder.ReadWavelengthSolution(ref_header, ref_data)
            self.reference_solution = fits_ws_reader.get_wavelength_solution()
        else:
            reference_plots_enabled = False
            log.error('Please Check the OBJECT Keyword of your reference data')

        """------- Plots -------"""
        self.i_fig = plt.figure(1)
        self.i_fig.canvas.set_window_title('Science Target: %s' % self.science_object.name)
        manager = plt.get_current_fig_manager()
        if plt.get_backend() == 'TkAgg':
            manager.resize(*manager.window.maxsize())
        elif plt.get_backend() == 'QT4Agg':
            manager.window.showMaximized()
        else:
            manager.window.maximize()
        # manager.window.attributes('-topmost', 0)
        self.ax1 = plt.subplot(211)
        self.ax1.set_title('Raw Data - %s' % self.lamp_name)
        self.ax1.set_xlabel('Pixels')
        self.ax1.set_ylabel('Intensity (counts)')
        for idline in self.lines_center:
            self.ax1.axvline(idline, linestyle='-.', color='r')
        self.ax1.plot(self.raw_pixel_axis, self.data0, color='b')
        self.ax1.set_xlim((0, 4096))

        self.ax2 = plt.subplot(212)
        self.ax2.set_title('Reference Data')
        self.ax2.set_xlabel('Wavelength (Angstrom)')
        self.ax2.set_ylabel('Intensity (counts)')
        self.ax2.axvline(self.blue_limit, color='k')
        self.ax2.axvline(self.center_wavelength, color='k')
        self.ax2.axvline(self.red_limit, color='k')
        for rline in self.reference_data.get_line_list_by_name(self.lamp_name):
            self.ax2.axvline(rline, linestyle=':', color='m', alpha=0.9)
        if reference_plots_enabled:
            self.ax2.plot(self.reference_solution[0], self.reference_solution[1], color='b')
            self.ax2.set_xlim((self.reference_solution[0][0], self.reference_solution[0][-1]))

        plt.subplots_adjust(left=0.04, right=0.99, top=0.97, bottom=0.04, hspace=0.17)
        self.raw_data_bb = self.ax1.get_position()
        self.reference_bb = self.ax2.get_position()

        if self.click_input_enabled:
            self.i_fig.canvas.mpl_connect('button_press_event', self.on_click)
            self.i_fig.canvas.mpl_connect('key_press_event', self.key_pressed)
            # print self.wsolution
            plt.show()
        return True

    def automatic_wavelength_solution(self):
        pass

    def update_clicks_plot(self, action):
        if action == 'reference':
            if self.points_ref is not None:
                try:
                    self.points_ref.remove()
                    self.ax2.relim()
                except:
                    pass
            self.points_ref, = self.ax2.plot(self.reference_clicks_x,
                                             self.reference_clicks_y,
                                             linestyle='None',
                                             marker='o',
                                             color='r')
            self.i_fig.canvas.draw()
        elif action == 'raw_data':
            # print self.points_raw
            # print dir(self.points_raw)
            if self.points_raw is not None:
                try:
                    self.points_raw.remove()
                    self.ax1.relim()
                except:
                    pass
            self.points_raw, = self.ax1.plot(self.raw_data_clicks_x,
                                             self.raw_data_clicks_y,
                                             linestyle='None',
                                             marker='o',
                                             color='r')
            self.i_fig.canvas.draw()
        elif action == 'delete':
            if self.points_raw is not None and self.points_ref is not None:
                self.points_raw.remove()
                self.ax1.relim()
                self.points_ref.remove()
                self.ax2.relim()
                self.i_fig.canvas.draw()

    def plot_raw_over_reference(self, remove=False):
        if self.wsolution is not None:
            if self.line_raw is not None:
                try:
                    self.line_raw.remove()
                    self.ax2.relim()
                except:
                    pass
            if not remove:
                # TODO (simon) catch TypeError Exception and correct what is causing it
                self.line_raw, = self.ax2.plot(self.wsolution(self.raw_pixel_axis),
                                               self.data0,
                                               linestyle='-',
                                               color='r')
            self.i_fig.canvas.draw()

    def evaluate_solution(self, plots=False):
        if self.wsolution is not None:
            square_differences = []
            wavelength_line_centers = self.wsolution(self.lines_center)

            for wline in wavelength_line_centers:
                closer_index = np.argmin(abs(self.reference_data.get_line_list_by_name(self.lamp_name) - wline))
                rline = self.reference_data.get_line_list_by_name(self.lamp_name)[closer_index]
                rw_difference = wline - rline
                # print 'Difference w - r ', rw_difference, rline
                square_differences.append(rw_difference ** 2)
            clipped_square_differences = sigma_clip(square_differences, sigma=3, iters=5)
            npoints = len(clipped_square_differences)
            n_rejections = np.ma.count_masked(clipped_square_differences)
            rms_error = np.sqrt(np.sum(clipped_square_differences) / len(clipped_square_differences))
            log.info('RMS Error : %s', rms_error)
            if plots:
                fig4 = plt.figure(4)
                fig4.canvas.set_window_title('Wavelength Solution')
                plt.plot(self.raw_pixel_axis, self.wsolution(self.raw_pixel_axis))
                plt.plot(self.raw_data_clicks_x, self.reference_clicks_x, marker='o', color='g')
                plt.xlabel('Pixel Axis')
                plt.ylabel('Wavelength Axis')
                plt.title('RMS Error %s with %s points and %s rejections' % (rms_error, npoints, n_rejections))
                plt.show()

            return [rms_error, npoints, n_rejections]
        else:
            log.error('Solution is still non-existent!')

    def fit_pixel_to_wavelength(self):
        if len(self.reference_clicks_x) and len(self.raw_data_clicks_x) > 0:
            pixel = []
            angstrom = []
            for i in range(len(self.reference_clicks_x)):
                pixel.append(self.raw_data_clicks_x[i])
                angstrom.append(self.reference_clicks_x[i])
            wavelength_solution = wsBuilder.WavelengthFitter(model='chebyshev', degree=3)
            self.wsolution = wavelength_solution.ws_fit(pixel, angstrom)
        else:
            log.error('Clicks record is empty')
            if self.wsolution is not None:
                self.wsolution = None

    def linearize_spectrum(self, data, plots=False):
        pixel_axis = range(1, len(data) + 1, 1)
        if self.wsolution is not None:
            x_axis = self.wsolution(pixel_axis)
            new_x_axis = np.linspace(x_axis[0], x_axis[-1], len(data))
            tck = scipy.interpolate.splrep(x_axis, data, s=0)
            linearized_data = scipy.interpolate.splev(new_x_axis, tck, der=0)
            if plots:
                fig6 = plt.figure(6)
                fig6.canvas.set_window_title('Linearized Data')
                plt.plot(x_axis, data, color='b')
                plt.plot(new_x_axis, linearized_data, color='r', linestyle=':')
                plt.tight_layout()
                plt.show()
                fig7 = plt.figure(7)
                fig7.canvas.set_window_title('Wavelength Solution')
                plt.plot(x_axis, color='b')
                plt.plot(new_x_axis, color='r')
                plt.tight_layout()
                plt.show()

            return [new_x_axis, linearized_data]

    def pixel_axis_cross_correlate(self, reference, lines_in_range, pixel_lines):

        root_pixel_axis = np.linspace(0, 4096, 4096)
        reference_axis = np.zeros(len(root_pixel_axis))
        pixel_lines_axis = np.zeros(len(root_pixel_axis))
        for ref_line in reference:
            gaussian = models.Gaussian1D(amplitude=1, mean=ref_line, stddev=5)
            reference_axis += gaussian(root_pixel_axis)
        for pix_line in pixel_lines:
            gaussian = models.Gaussian1D(amplitude=1, mean=pix_line, stddev=5)
            pixel_lines_axis += gaussian(root_pixel_axis)

        """Cross correlate"""
        lag_position = range(-400, 400, 1)
        correlation = []
        for lag in lag_position:
            correlation_value = 0
            for i in range(len(reference_axis)):
                i_ref = i
                i_com = i + lag
                if 0 < i_com < len(reference_axis):
                    correlation_value += reference_axis[i_ref] * pixel_lines_axis[i_com]
            correlation.append(correlation_value)
        i_max = np.argmax(correlation)

        """
        plt.clf()
        plt.title('Lag Position: %s' % lag_position[i_max])
        plt.axvline(lag_position[i_max])
        plt.plot(lag_position, correlation)
        plt.show()


        plt.plot(root_pixel_axis, reference_axis, color='g', label='Reference')
        plt.plot(root_pixel_axis, pixel_lines_axis, color='r', label='Lines')
        plt.legend(loc='best')
        plt.show()
        # """
        return lag_position[i_max]

    def add_wavelength_solution(self, new_header, spectrum, original_filename, evaluation_comment=None):
        if evaluation_comment is None:
            rms_error, n_points, n_rejections = self.evaluate_solution()
            self.evaluation_comment = 'Lamp Solution RMSE = %s Npoints = %s, NRej = %s' % (rms_error,
                                                                                    n_points,
                                                                                    n_rejections)
            new_header['COMMENT'] = self.evaluation_comment
        else:
            new_header['COMMENT'] = evaluation_comment

        new_crpix = 1
        new_crval = spectrum[0][new_crpix - 1]
        new_cdelt = spectrum[0][new_crpix] - spectrum[0][new_crpix - 1]

        new_header['BANDID1'] = 'spectrum - background none, weights none, clean no'
        # new_header['APNUM1'] = '1 1 1452.06 1454.87'
        new_header['WCSDIM'] = 1
        new_header['CTYPE1'] = 'LINEAR  '
        new_header['CRVAL1'] = new_crval
        new_header['CRPIX1'] = new_crpix
        new_header['CDELT1'] = new_cdelt
        new_header['CD1_1'] = new_cdelt
        new_header['LTM1_1'] = 1.
        new_header['WAT0_001'] = 'system=equispec'
        new_header['WAT1_001'] = 'wtype=linear label=Wavelength units=angstroms'
        new_header['DC-FLAG'] = 0
        new_header['DCLOG1'] = 'REFSPEC1 = %s' % self.calibration_lamp

        new_filename = self.args.destiny + self.args.output_prefix + original_filename

        fits.writeto(new_filename, spectrum[1], new_header, clobber=True)
        # print new_header
        return new_header

    @staticmethod
    def get_wavelength_solution(header):
        """Reproduces wavelength solution from the image's header



        Args:
            header:

        Returns:

        """
        ctype1 = header['CTYPE1']
        if ctype1 == 'LINEAR':
            reference_value = float(header['CRVAL1'])
            reference_pixel = int(header['CRPIX1'])
            delta = float(header['CDELT1'])
            text = header['WAT1_001'].split()
            text_dict = {}
            for value in text:
                key, val = value.split('=')
                text_dict[key] = val
            if int(header['NAXIS']) == 1:
                length = int(header['NAXIS1'])
                start = reference_value - (reference_pixel - 1) * delta
                stop = start + (length - 1) * delta
                log.debug('Start %s Stop %s Length %s', start, stop, length)
                wavelength_axis = np.linspace(start, stop, length)
                return wavelength_axis
            else:
                log.error('Can not work with multi-axis files.')
                return False
        elif ctype1 == 'MULTISPE':
            if int(header['WCSDIM']) == 2:
                try:
                    ctype2 = header['CTYPE2']
                    if ctype2 == 'MULTISPE':
                        cdelt2 = header['CDELT2']
                        cd22 = header['CD2_2']
                        ltm22 = header['LTM2_2']
                        waxmap01 = header['WAXMAP01']
                        wat2_keys = header['WAT2_*']
                        wat2 = ''
                        for key in wat2_keys:
                            wat2 += header[key]

                        wat = wat2.split('"')
                        """
                        taken from ftp://iraf.noao.edu/iraf/web/projects/fitswcs/specwcs.html
                        and http://shaileshahuja.blogspot.cl/2014/06/analysing-iraf-multispec-format-fits.html
                        wat index and meaning
                        0 : Aperture
                        1 : Beam
                        2 : dtype
                            -1 Spectrum not calibrated
                            0 Linear dispersion sampling
                            1 Log-linear dispersion
                            2 Nonlinear dispersion.
                        3 : Dispersion Value at start
                        4 : Average Dispersion delta
                        5 : Number of Pixels
                        6 : Doppler Factor
                        7 : Aperture Low
                        8 : Aperture High
                        ---
                        9 : Weight
                        10 : Zero-point offset
                        11 : Function type
                            1 Chebyshev polynomial
                            2 Legendre polynomial
                            3 Cubic spline
                            4 Linear spline
                            5 Pixel coordinate array
                            6 Sampled coordinate array
                        12 : Order of function
                        13 : Minimum Pixel Value
                        14 : Maximum Pixel Value
                        15+ : Coefficients of functions i

                        """

                        if 'spec' not in wat[1]:
                            print(True)

                        print(wat2)
                        print(wat[1])
                        aperture = wat[1][0]
                        beam = wat[1][1]
                        dtype = wat[1][2]

                    else:
                        log.debug('Nothing to do!')
                except KeyError:
                    log.error('KeyError')
        elif ctype1 == 'PIXEL':
            log.error('This header does not contain a wavelength solution')
            return False

    def recenter_line_by_data(self, data_name, x):
        if data_name == 'reference':
            pseudo_center = np.argmin(abs(self.reference_solution[0] - x))
            reference_line_index = np.argmin(abs(self.reference_data.get_line_list_by_name(self.lamp_name) - x))
            reference_line_value = self.reference_data.get_line_list_by_name(self.lamp_name)[reference_line_index]
            sub_x = self.reference_solution[0][pseudo_center - 10: pseudo_center + 10]
            sub_y = self.reference_solution[1][pseudo_center - 10: pseudo_center + 10]
            center_of_mass = np.sum(sub_x * sub_y) / np.sum(sub_y)
            # print 'centroid ', center_of_mass
            fig2 = plt.figure(3)
            plt.plot(sub_x, sub_y)
            plt.axvline(center_of_mass)
            plt.axvline(reference_line_value, color='r')
            plt.show()
            # return center_of_mass
            return reference_line_value
        elif data_name == 'raw-data':
            pseudo_center = np.argmin(abs(self.raw_pixel_axis - x))
            sub_x = self.raw_pixel_axis[pseudo_center - 10: pseudo_center + 10]
            sub_y = self.data0[pseudo_center - 10: pseudo_center + 10]
            center_of_mass = np.sum(sub_x * sub_y) / np.sum(sub_y)
            # print 'centroid ', center_of_mass
            fig2 = plt.figure(3)
            plt.plot(sub_x, sub_y)
            plt.axvline(center_of_mass)
            plt.show()
            return center_of_mass
        else:
            log.error('Unrecognized data name')

    def on_click(self, event):
        # print event.button
        self.events = True
        if event.button == 2:
            if event.xdata is not None and event.ydata is not None:
                ix, iy = self.i_fig.transFigure.inverted().transform((event.x, event.y))
                if self.reference_bb.contains(ix, iy):
                    # self.reference_clicks.append([event.xdata, event.ydata])
                    self.reference_clicks_x.append(self.recenter_line_by_data('reference', event.xdata))
                    self.reference_clicks_y.append(event.ydata)
                    self.update_clicks_plot('reference')
                elif self.raw_data_bb.contains(ix, iy):
                    # self.raw_data_clicks.append([event.xdata, event.ydata])
                    self.raw_data_clicks_x.append(self.recenter_line_by_data('raw-data', event.xdata))
                    self.raw_data_clicks_y.append(event.ydata)
                    self.update_clicks_plot('raw_data')
                # self.ref_click_plot.set_xdata(np.array(self.reference_clicks[:][0]))
                # self.ref_click_plot.set_ydata(np.array(self.reference_clicks[:][1]))
                # self.ref_click_plot.draw()
                else:
                    print ix, iy, 'Are not contained'
                # print 'click ', event.xdata, ' ', event.ydata, ' ', event.button
                # print event.x, event.y
            else:
                log.error('Clicked Region is out of boundary')
        elif event.button == 3:
            if len(self.reference_clicks) == len(self.raw_data_clicks):
                self.click_input_enabled = False
                log.info('Leaving interactive mode')
            else:
                if len(self.reference_clicks) < len(self.raw_data_clicks):
                    log.info('There is %s click missing in the Reference plot',
                             len(self.raw_data_clicks) - len(self.reference_clicks))
                else:
                    log.info('There is %s click missing in the New Data plot',
                             len(self.reference_clicks) - len(self.raw_data_clicks))

    def key_pressed(self, event):
        self.events = True
        if event.key == 'f1':
            log.info('Print help regarding interactive mode')
            print("F1 : Prints Help.")
            print("F2 : Fit wavelength solution model.")
            print("F3 : Find new lines.")
            print("F4 : Evaluate solution")
            print("F6 : Linearize data (for testing not definitive)")
            print("d : deletes closest point")
            # print("l : resample spectrum to a linear dispersion axis")
            print("ctrl+d : deletes all recorded clicks")
            print("ctrl+b : Go back to previous solution (deletes automatic added points")
            print('Middle Button Click: records data location.')
            print("Right Button Click: Leaves interactive mode.")
        elif event.key == 'f2':
            log.debug('Calling function to fit wavelength Solution')
            self.fit_pixel_to_wavelength()
            self.plot_raw_over_reference()
        elif event.key == 'f3':
            if self.wsolution is not None:
                self.find_more_lines()
                self.update_clicks_plot('reference')
                self.update_clicks_plot('raw_data')
        elif event.key == 'f4':
            if self.wsolution is not None and len(self.raw_data_clicks_x) > 0:
                self.evaluate_solution(plots=True)
        elif event.key == 'd':
            ix, iy = self.i_fig.transFigure.inverted().transform((event.x, event.y))
            if self.raw_data_bb.contains(ix, iy):
                print 'Deleting point'
                # print abs(self.raw_data_clicks_x - event.xdata)
                closer_index = int(np.argmin(abs(self.raw_data_clicks_x - event.xdata)))
                # print 'Index ', closer_index
                if len(self.raw_data_clicks_x) == len(self.reference_clicks_x):
                    self.raw_data_clicks_x.pop(closer_index)
                    self.raw_data_clicks_y.pop(closer_index)
                    self.reference_clicks_x.pop(closer_index)
                    self.reference_clicks_y.pop(closer_index)
                    self.update_clicks_plot('reference')
                    self.update_clicks_plot('raw_data')
                else:
                    self.raw_data_clicks_x.pop(closer_index)
                    self.raw_data_clicks_y.pop(closer_index)
                    self.update_clicks_plot('raw_data')
            elif self.reference_bb.contains(ix, iy):
                print 'Deleting point'
                # print 'reference ', self.reference_clicks_x, self.re
                # print self.reference_clicks_x
                # print abs(self.reference_clicks_x - event.xdata)
                closer_index = int(np.argmin(abs(self.reference_clicks_x - event.xdata)))
                if len(self.raw_data_clicks_x) == len(self.reference_clicks_x):
                    self.raw_data_clicks_x.pop(closer_index)
                    self.raw_data_clicks_y.pop(closer_index)
                    self.reference_clicks_x.pop(closer_index)
                    self.reference_clicks_y.pop(closer_index)
                    self.update_clicks_plot('reference')
                    self.update_clicks_plot('raw_data')
                else:
                    self.reference_clicks_x.pop(closer_index)
                    self.reference_clicks_y.pop(closer_index)
                    self.update_clicks_plot('reference')
        elif event.key == 'f6':
            log.info('Linearize spectrum')
            if self.wsolution is not None:
                self.linearize_spectrum(self.data0, plots=True)
        elif event.key == 'ctrl+b':
            log.info('Deleting automatic added points. If exist.')
            if self.raw_data_clicks_x is not [] and self.reference_clicks_x is not []:
                to_remove = []
                for i in range(len(self.raw_data_clicks_x)):
                    # print self.raw_data_clicks[i], self.filling_value
                    if self.raw_data_clicks_y[i] == self.filling_value:
                        to_remove.append(i)
                        # print to_remove
                to_remove = np.array(sorted(to_remove, reverse=True))
                if len(to_remove) > 0:
                    for index in to_remove:
                        self.raw_data_clicks_x.pop(index)
                        self.raw_data_clicks_y.pop(index)
                        self.reference_clicks_x.pop(index)
                        self.reference_clicks_y.pop(index)
                    self.update_clicks_plot('reference')
                    self.update_clicks_plot('raw_data')
                    # else:
                    # print self.raw_click_plot, self.ref_click_plot, 'mmm'
        elif event.key == 'ctrl+d':
            log.info('Deleting all recording Clicks')
            answer = raw_input('Are you sure you want to delete all clicks? only typing "No" will stop it! : ')
            if answer.lower() != 'no':
                self.reference_clicks_x = []
                self.reference_clicks_y = []
                self.raw_data_clicks_x = []
                self.raw_data_clicks_y = []
                self.update_clicks_plot('delete')
                self.plot_raw_over_reference(remove=True)
            else:
                log.info('No click was deleted this time!.')
        else:
            # print event.key
            pass


class WavelengthSolution:
    def __init__(self, solution_type=None, model_name=None, model_order=0, model=None, ref_lamp=None, eval_comment=''):
        self.dtype_dict = {None: -1, 'linear': 0, 'log_linear': 1, 'non_linear': 2}
        # if solution_type == 'non_linear' and model_name is not None:
        self.ftype_dict = {'chebyshev': 1,
                           'legendre': 2,
                           'cubic_spline': 3,
                           'linear_spline': 4,
                           'pixel_coords': 5,
                           'samples_coords': 6,
                           None: None}
        self.solution_type = solution_type
        self.model_name = model_name
        self.model_order = model_order
        self.wsolution = model
        self.reference_lamp = ref_lamp
        self.evaluation_comment = eval_comment
        self.aperture = 1  # aperture number
        self.beam = 1  # beam
        self.dtype = self.dtype_dict[solution_type]  # data type
        self.w1 = 0  # dispersion at start
        self.dw = 0  # dispersion delta average
        self.nw = 0  # pixel number
        self.z = 0  # doppler factor
        self.aplow = 0  # aperture low (pix)
        self.aphigh = 0  # aperture high
        # funtions parameters
        self.weight = 1
        self.zeropoint = 0
        self.ftype = self.ftype_dict[model_name]  # function type
        self.forder = model_order  # function order
        self.pmin = 0  # minimum pixel value
        self.pmax = 0  # maximum pixel value
        self.fpar = []  # function parameters

    def linear_solution_string(self, header):
        pass


if __name__ == '__main__':
    wav_cal = WavelengthCalibration()
