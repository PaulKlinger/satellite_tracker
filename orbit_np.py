import numpy as np
from datetime import datetime, timedelta

ECC_EPS = 1.0e-6  # Too low for computing further drops.
ECC_LIMIT_LOW = -1.0e-3
ECC_LIMIT_HIGH = 1.0 - ECC_EPS  # Too close to 1
ECC_ALL = 1.0e-4

EPS_COS = 1.5e-12

NR_EPS = 1.0e-12

CK2 = 5.413080e-4
CK4 = 0.62098875e-6
E6A = 1.0e-6
QOMS2T = 1.88027916e-9
S = 1.01222928
S0 = 78.0
XJ3 = -0.253881e-5
XKE = 0.743669161e-1
XKMPER = 6378.135
XMNPDA = 1440.0
# MFACTOR = 7.292115E-5
AE = 1.0
SECDAY = 8.6400E4

F = 1 / 298.257223563  # Earth flattening WGS-84
A = 6378.137  # WGS84 Equatorial radius

SGDP4_ZERO_ECC = 0
SGDP4_DEEP_NORM = 1
SGDP4_NEAR_SIMP = 2
SGDP4_NEAR_NORM = 3

KS = AE * (1.0 + S0 / XKMPER)
A3OVK2 = (-XJ3 / CK2) * AE ** 3


class OrbitalError(Exception):
    pass


def dt2np(utc_time):
    try:
        return np.datetime64(utc_time)
    except ValueError:
        return utc_time.astype('datetime64[ns]')


def jdays2000(utc_time):
    """Get the days since year 2000.
    """
    return _days(utc_time - np.datetime64('2000-01-01T12:00'))


def _days(dt):
    """Get the days (floating point) from *d_t*.
    """
    return dt / np.timedelta64(1, 'D')


def gmst(utc_time):
    """Greenwich mean sidereal utc_time, in radians.

    As defined in the AIAA 2006 implementation:
    http://www.celestrak.com/publications/AIAA/2006-6753/
    """
    ut1 = jdays2000(utc_time) / 36525.0
    theta = 67310.54841 + ut1 * (876600 * 3600 + 8640184.812866 + ut1 *
                                 (0.093104 - ut1 * 6.2 * 10e-6))
    return np.deg2rad(theta / 240.0) % (2 * np.pi)


class ChecksumError(Exception):
    '''ChecksumError.
    '''
    pass


class Tle(object):
    """Class holding TLE objects.
   """

    def __init__(self, line1=None, line2=None):
        self._line1 = line1
        self._line2 = line2

        self.satnumber = None
        self.classification = None
        self.id_launch_year = None
        self.id_launch_number = None
        self.id_launch_piece = None
        self.epoch_year = None
        self.epoch_day = None
        self.epoch = None
        self.mean_motion_derivative = None
        self.mean_motion_sec_derivative = None
        self.bstar = None
        self.ephemeris_type = None
        self.element_number = None
        self.inclination = None
        self.right_ascension = None
        self.excentricity = None
        self.arg_perigee = None
        self.mean_anomaly = None
        self.mean_motion = None
        self.orbit = None

        self._read_tle()
        self._checksum()
        self._parse_tle()

    @property
    def line1(self):
        '''Return first TLE line.'''
        return self._line1

    @property
    def line2(self):
        '''Return second TLE line.'''
        return self._line2

    @property
    def platform(self):
        '''Return satellite platform name.'''
        return self._platform

    def _checksum(self):
        """Performs the checksum for the current TLE.
        """
        for line in [self._line1, self._line2]:
            check = 0
            for char in line[:-1]:
                if char.isdigit():
                    check += int(char)
                if char == "-":
                    check += 1

            if (check % 10) != int(line[-1]):
                raise ChecksumError(self._platform + " " + line)

    def _read_tle(self):
        '''Read TLE data.
        '''

        if self._line1 is not None and self._line2 is not None:
            tle = self._line1.strip() + "\n" + self._line2.strip()

        else:
            raise ValueError("No tle data")
        self._line1, self._line2 = tle.split('\n')

    def _parse_tle(self):
        '''Parse values from TLE data.
        '''

        def _read_tle_decimal(rep):
            '''Convert *rep* to decimal value.
            '''
            if rep[0] in ["-", " ", "+"]:
                digits = rep[1:-2].strip()
                val = rep[0] + "." + digits + "e" + rep[-2:]
            else:
                digits = rep[:-2].strip()
                val = "." + digits + "e" + rep[-2:]

            return float(val)

        self.satnumber = self._line1[2:7]
        self.classification = self._line1[7]
        self.id_launch_year = self._line1[9:11]
        self.id_launch_number = self._line1[11:14]
        self.id_launch_piece = self._line1[14:17]
        self.epoch_year = self._line1[18:20]
        self.epoch_day = float(self._line1[20:32])
        self.epoch = \
            np.datetime64(datetime.strptime(self.epoch_year, "%y") +
                          timedelta(days=self.epoch_day - 1), 'us')
        self.mean_motion_derivative = float(self._line1[33:43])
        self.mean_motion_sec_derivative = _read_tle_decimal(self._line1[44:52])
        self.bstar = _read_tle_decimal(self._line1[53:61])
        try:
            self.ephemeris_type = int(self._line1[62])
        except ValueError:
            self.ephemeris_type = 0
        self.element_number = int(self._line1[64:68])

        self.inclination = float(self._line2[8:16])
        self.right_ascension = float(self._line2[17:25])
        self.excentricity = int(self._line2[26:33]) * 10 ** -7
        self.arg_perigee = float(self._line2[34:42])
        self.mean_anomaly = float(self._line2[43:51])
        self.mean_motion = float(self._line2[52:63])
        self.orbit = int(self._line2[63:68])

    def __str__(self):
        import pprint
        import sys
        from io import StringIO
        s_var = StringIO()
        d_var = dict(([(k, v) for k, v in
                       list(self.__dict__.items()) if k[0] != '_']))
        pprint.pprint(d_var, s_var)
        return s_var.getvalue()[:-1]


class OrbitElements(object):
    """Class holding the orbital elements.
    """

    def __init__(self, tles):
        self.epoch = np.array([tle.epoch for tle in tles])
        self.excentricity = np.array([tle.excentricity for tle in tles])
        self.inclination = np.array([np.deg2rad(tle.inclination) for tle in tles])
        self.right_ascension = np.array([np.deg2rad(tle.right_ascension) for tle in tles])
        self.arg_perigee = np.array([np.deg2rad(tle.arg_perigee) for tle in tles])
        self.mean_anomaly = np.array([np.deg2rad(tle.mean_anomaly) for tle in tles])

        self.mean_motion = np.array([tle.mean_motion * (np.pi * 2 / XMNPDA) for tle in tles])
        self.mean_motion_derivative = np.array([tle.mean_motion_derivative * \
                                                np.pi * 2 / XMNPDA ** 2 for tle in tles])
        self.mean_motion_sec_derivative = np.array([tle.mean_motion_sec_derivative * \
                                                    np.pi * 2 / XMNPDA ** 3 for tle in tles])
        self.bstar = np.array([tle.bstar * AE for tle in tles])

        n_0 = self.mean_motion
        k_e = XKE
        k_2 = CK2
        i_0 = self.inclination
        e_0 = self.excentricity

        a_1 = (k_e / n_0) ** (2.0 / 3)
        delta_1 = ((3 / 2.0) * (k_2 / a_1 ** 2) * ((3 * np.cos(i_0) ** 2 - 1) /
                                                   (1 - e_0 ** 2) ** (2.0 / 3)))

        a_0 = a_1 * (1 - delta_1 / 3 - delta_1 ** 2 - (134.0 / 81) * delta_1 ** 3)

        delta_0 = ((3 / 2.0) * (k_2 / a_0 ** 2) * ((3 * np.cos(i_0) ** 2 - 1) /
                                                   (1 - e_0 ** 2) ** (2.0 / 3)))

        # original mean motion
        n_0pp = n_0 / (1 + delta_0)
        self.original_mean_motion = n_0pp

        # semi major axis
        a_0pp = a_0 / (1 - delta_0)
        self.semi_major_axis = a_0pp

        self.period = np.pi * 2 / n_0pp

        self.perigee = (a_0pp * (1 - e_0) / AE - AE) * XKMPER

        self.right_ascension_lon = (self.right_ascension
                                    - gmst(self.epoch))

        self.right_ascension_lon = np.where(self.right_ascension_lon > np.pi,
                                            self.right_ascension_lon - 2 * np.pi,
                                            self.right_ascension_lon)


class _SGDP4(object):
    """Class for the SGDP4 computations.
    """

    def __init__(self, orbit_elements):
        self.mode = None

        perigee = orbit_elements.perigee
        self.eo = orbit_elements.excentricity
        self.xincl = orbit_elements.inclination
        self.xno = orbit_elements.original_mean_motion
        k_2 = CK2
        k_4 = CK4
        k_e = XKE
        self.bstar = orbit_elements.bstar
        self.omegao = orbit_elements.arg_perigee
        self.xmo = orbit_elements.mean_anomaly
        self.xnodeo = orbit_elements.right_ascension
        self.t_0 = orbit_elements.epoch
        self.xn_0 = orbit_elements.mean_motion
        A30 = -XJ3 * AE ** 3

        self.errors = np.logical_not(np.logical_and(0 < self.eo, self.eo < ECC_LIMIT_HIGH))
        self.errors = np.logical_or(self.errors, (
            np.logical_not(((0.0035 * 2 * np.pi / XMNPDA) < self.xn_0) & (self.xn_0 < (18 * 2 * np.pi / XMNPDA)))))
        self.errors = np.logical_or(self.errors, (np.logical_not((0 < self.xincl) & (self.xincl < np.pi))))

        self.errors = np.logical_or(self.errors, self.eo < 0)

        self.cosIO = np.cos(self.xincl)
        self.sinIO = np.sin(self.xincl)
        theta2 = self.cosIO ** 2
        theta4 = theta2 ** 2
        self.x3thm1 = 3.0 * theta2 - 1.0
        self.x1mth2 = 1.0 - theta2
        self.x7thm1 = 7.0 * theta2 - 1.0

        a1 = (XKE / self.xn_0) ** (2. / 3)
        betao2 = 1.0 - self.eo ** 2
        betao = np.sqrt(betao2)
        temp0 = 1.5 * CK2 * self.x3thm1 / (betao * betao2)
        del1 = temp0 / (a1 ** 2)
        a0 = a1 * \
             (1.0 - del1 * (1.0 / 3.0 + del1 * (1.0 + del1 * 134.0 / 81.0)))
        del0 = temp0 / (a0 ** 2)
        self.xnodp = self.xn_0 / (1.0 + del0)
        self.aodp = (a0 / (1.0 - del0))
        self.perigee = (self.aodp * (1.0 - self.eo) - AE) * XKMPER
        self.apogee = (self.aodp * (1.0 + self.eo) - AE) * XKMPER
        self.period = (2 * np.pi * 1440.0 / XMNPDA) / self.xnodp

        # set error for modes other than SGDP4_NEAR_NORM
        self.errors = np.logical_or.reduce((self.errors, self.period >= 225, self.perigee < 220))

        # if self.period >= 225:
        #    # Deep-Space model
        #    self.mode = SGDP4_DEEP_NORM
        # elif self.perigee < 220:
        #    # Near-space, simplified equations
        #    self.mode = SGDP4_NEAR_SIMP
        # else:
        #    # Near-space, normal equations
        #    self.mode = SGDP4_NEAR_NORM

        s4 = np.where(self.perigee < 156, np.maximum(self.perigee - 78, 20), KS)
        qoms24 = np.where(self.perigee < 156, ((120 - s4) * (AE / XKMPER)) ** 4, QOMS2T)
        s4 = np.where(self.perigee < 156, s4 / XKMPER + AE, s4)

        pinvsq = 1.0 / (self.aodp ** 2 * betao2 ** 2)
        tsi = 1.0 / (self.aodp - s4)
        self.eta = self.aodp * self.eo * tsi
        etasq = self.eta ** 2
        eeta = self.eo * self.eta
        psisq = np.abs(1.0 - etasq)
        coef = qoms24 * tsi ** 4
        coef_1 = coef / psisq ** 3.5

        self.c2 = (coef_1 * self.xnodp * (self.aodp *
                                          (1.0 + 1.5 * etasq + eeta * (4.0 + etasq)) +
                                          (0.75 * CK2) * tsi / psisq * self.x3thm1 *
                                          (8.0 + 3.0 * etasq * (8.0 + etasq))))

        self.c1 = self.bstar * self.c2

        self.c4 = (2.0 * self.xnodp * coef_1 * self.aodp * betao2 * (self.eta *
                                                                     (2.0 + 0.5 * etasq) + self.eo * (0.5 + 2.0 *
                                                                                                      etasq) - (
                                                                             2.0 * CK2) * tsi / (
                                                                             self.aodp * psisq) * (-3.0 *
                                                                                                   self.x3thm1 * (
                                                                                                           1.0 - 2.0 * eeta + etasq *
                                                                                                           (
                                                                                                                   1.5 - 0.5 * eeta)) + 0.75 * self.x1mth2 * (
                                                                                                           2.0 *
                                                                                                           etasq - eeta * (
                                                                                                                   1.0 + etasq)) * np.cos(
                            2.0 * self.omegao))))

        self.c5, self.c3, self.omgcof = 0.0, 0.0, 0.0

        self.c5 = (2.0 * coef_1 * self.aodp * betao2 *
                   (1.0 + 2.75 * (etasq + eeta) + eeta * etasq))

        self.c3 = np.where(self.eo > ECC_ALL, coef * tsi * A3OVK2 * \
                           self.xnodp * AE * self.sinIO / self.eo, self.c3)

        self.omgcof = self.bstar * self.c3 * np.cos(self.omegao)

        temp1 = 3.0 * CK2 * pinvsq * self.xnodp
        temp2 = temp1 * CK2 * pinvsq
        temp3 = 1.25 * CK4 * pinvsq ** 2 * self.xnodp

        self.xmdot = (self.xnodp + (0.5 * temp1 * betao * self.x3thm1 + 0.0625 *
                                    temp2 * betao * (13.0 - 78.0 * theta2 +
                                                     137.0 * theta4)))

        x1m5th = 1.0 - 5.0 * theta2

        self.omgdot = (-0.5 * temp1 * x1m5th + 0.0625 * temp2 *
                       (7.0 - 114.0 * theta2 + 395.0 * theta4) +
                       temp3 * (3.0 - 36.0 * theta2 + 49.0 * theta4))

        xhdot1 = -temp1 * self.cosIO
        self.xnodot = (xhdot1 + (0.5 * temp2 * (4.0 - 19.0 * theta2) +
                                 2.0 * temp3 * (3.0 - 7.0 * theta2)) * self.cosIO)

        self.xmcof = np.where(self.eo > ECC_ALL, (-(2. / 3) * AE) * coef * self.bstar / eeta, 0.0)

        self.xnodcf = 3.5 * betao2 * xhdot1 * self.c1
        self.t2cof = 1.5 * self.c1

        # Check for possible divide-by-zero for X/(1+cos(xincl)) when
        # calculating xlcof */
        temp0 = 1.0 + self.cosIO
        temp0 = np.where(np.abs(temp0) < EPS_COS, np.sign(temp0) * EPS_COS, temp0)

        self.xlcof = 0.125 * A3OVK2 * self.sinIO * \
                     (3.0 + 5.0 * self.cosIO) / temp0

        self.aycof = 0.25 * A3OVK2 * self.sinIO

        self.cosXMO = np.cos(self.xmo)
        self.sinXMO = np.sin(self.xmo)
        self.delmo = (1.0 + self.eta * self.cosXMO) ** 3

        c1sq = self.c1 ** 2
        self.d2 = 4.0 * self.aodp * tsi * c1sq
        temp0 = self.d2 * tsi * self.c1 / 3.0
        self.d3 = (17.0 * self.aodp + s4) * temp0
        self.d4 = 0.5 * temp0 * self.aodp * tsi * \
                  (221.0 * self.aodp + 31.0 * s4) * self.c1
        self.t3cof = self.d2 + 2.0 * c1sq
        self.t4cof = 0.25 * \
                     (3.0 * self.d3 + self.c1 * (12.0 * self.d2 + 10.0 * c1sq))
        self.t5cof = (0.2 * (3.0 * self.d4 + 12.0 * self.c1 * self.d3 + 6.0 * self.d2 ** 2 +
                             15.0 * c1sq * (2.0 * self.d2 + c1sq)))

    def propagate(self, utc_time):
        prop_errors = self.errors.copy()

        kep = {}

        # get the time delta in minutes
        # ts = astronomy._days(utc_time - self.t_0) * XMNPDA
        # print utc_time.shape
        # print self.t_0
        utc_time = dt2np(utc_time)
        ts = (utc_time - self.t_0) / np.timedelta64(1, 'm')

        em = self.eo
        xinc = self.xincl

        xmp = self.xmo + self.xmdot * ts
        xnode = self.xnodeo + ts * (self.xnodot + ts * self.xnodcf)
        omega = self.omegao + self.omgdot * ts

        delm = self.xmcof * \
               ((1.0 + self.eta * np.cos(xmp)) ** 3 - self.delmo)
        temp0 = ts * self.omgcof + delm
        xmp += temp0
        omega -= temp0
        tempa = 1.0 - \
                (ts *
                 (self.c1 + ts * (self.d2 + ts * (self.d3 + ts * self.d4))))
        tempe = self.bstar * \
                (self.c4 * ts + self.c5 * (np.sin(xmp) - self.sinXMO))
        templ = ts * ts * \
                (self.t2cof + ts *
                 (self.t3cof + ts * (self.t4cof + ts * self.t5cof)))
        a = self.aodp * tempa ** 2
        e = em - tempe
        xl = xmp + omega + xnode + self.xnodp * templ

        prop_errors = prop_errors | (a < 1)  # crashed
        prop_errors = prop_errors | (e < ECC_LIMIT_LOW)  # modified eccentricity too low

        e = np.where(e < ECC_EPS, ECC_EPS, e)
        e = np.where(e > ECC_LIMIT_HIGH, ECC_LIMIT_HIGH, e)

        beta2 = 1.0 - e ** 2

        # Long period periodics
        sinOMG = np.sin(omega)
        cosOMG = np.cos(omega)

        temp0 = 1.0 / (a * beta2)
        axn = e * cosOMG
        ayn = e * sinOMG + temp0 * self.aycof
        xlt = xl + temp0 * self.xlcof * axn

        elsq = axn ** 2 + ayn ** 2

        prop_errors |= (elsq >= 1) # e**2 >= 1

        kep['ecc'] = np.sqrt(elsq)

        epw = np.fmod(xlt - xnode, 2 * np.pi)
        # needs a copy in case of an array
        capu = np.array(epw)
        maxnr = kep['ecc']
        for i in range(10):
            sinEPW = np.sin(epw)
            cosEPW = np.cos(epw)

            ecosE = axn * cosEPW + ayn * sinEPW
            esinE = axn * sinEPW - ayn * cosEPW
            f = capu - epw + esinE
            if np.all(np.abs(f) < NR_EPS):
                break

            df = 1.0 - ecosE

            # 1st order Newton-Raphson correction.
            nr = f / df

            # 2nd order Newton-Raphson correction.
            nr = np.where(np.logical_and(i == 0, np.abs(nr) > 1.25 * maxnr),
                          np.sign(nr) * maxnr,
                          f / (df + 0.5 * esinE * nr))
            epw += nr

        # Short period preliminary quantities
        temp0 = 1.0 - elsq
        betal = np.sqrt(temp0)
        pl = a * temp0
        r = a * (1.0 - ecosE)
        invR = 1.0 / r
        temp2 = a * invR
        temp3 = 1.0 / (1.0 + betal)
        cosu = temp2 * (cosEPW - axn + ayn * esinE * temp3)
        sinu = temp2 * (sinEPW - ayn - axn * esinE * temp3)
        u = np.arctan2(sinu, cosu)
        sin2u = 2.0 * sinu * cosu
        cos2u = 2.0 * cosu ** 2 - 1.0
        temp0 = 1.0 / pl
        temp1 = CK2 * temp0
        temp2 = temp1 * temp0

        # Update for short term periodics to position terms.

        rk = r * (1.0 - 1.5 * temp2 * betal * self.x3thm1) + \
             0.5 * temp1 * self.x1mth2 * cos2u
        uk = u - 0.25 * temp2 * self.x7thm1 * sin2u
        xnodek = xnode + 1.5 * temp2 * self.cosIO * sin2u
        xinck = xinc + 1.5 * temp2 * self.cosIO * self.sinIO * cos2u

        prop_errors |= rk < 1 # crashed

        temp0 = np.sqrt(a)
        temp2 = XKE / (a * temp0)
        rdotk = ((XKE * temp0 * esinE * invR - temp2 * temp1 * self.x1mth2 * sin2u) *
                 (XKMPER / AE * XMNPDA / 86400.0))
        rfdotk = ((XKE * np.sqrt(pl) * invR + temp2 * temp1 *
                   (self.x1mth2 * cos2u + 1.5 * self.x3thm1)) *
                  (XKMPER / AE * XMNPDA / 86400.0))

        kep['radius'] = (rk * XKMPER / AE)[~prop_errors]
        kep['theta'] = uk[~prop_errors]
        kep['eqinc'] = xinck[~prop_errors]
        kep['ascn'] = xnodek[~prop_errors]
        kep['argp'] = omega[~prop_errors]
        kep['smjaxs'] = (a * XKMPER / AE)[~prop_errors]
        kep['rdotk'] = rdotk[~prop_errors]
        kep['rfdotk'] = rfdotk[~prop_errors]

        return kep, prop_errors


def kep2xyz(kep):
    sinT = np.sin(kep['theta'])
    cosT = np.cos(kep['theta'])
    sinI = np.sin(kep['eqinc'])
    cosI = np.cos(kep['eqinc'])
    sinS = np.sin(kep['ascn'])
    cosS = np.cos(kep['ascn'])

    xmx = -sinS * cosI
    xmy = cosS * cosI

    ux = xmx * sinT + cosS * cosT
    uy = xmy * sinT + sinS * cosT
    uz = sinI * sinT

    x = kep['radius'] * ux
    y = kep['radius'] * uy
    z = kep['radius'] * uz

    vx = xmx * cosT - cosS * sinT
    vy = xmy * cosT - sinS * sinT
    vz = sinI * cosT

    v_x = kep['rdotk'] * ux + kep['rfdotk'] * vx
    v_y = kep['rdotk'] * uy + kep['rfdotk'] * vy
    v_z = kep['rdotk'] * uz + kep['rfdotk'] * vz

    return np.array((x, y, z)), np.array((v_x, v_y, v_z))


class Orbitals(object):
    """Class for orbital computations.

    The *satellite* parameter is the name of the satellite to work on and is
    used to retreive the right TLE data for internet or from *tle_file* in case
    it is provided.
    """

    def __init__(self, tles):
        self.tles = np.array([Tle(line1=line1, line2=line2) for (line1, line2) in tles])
        self.orbit_elements = OrbitElements(self.tles)
        self._sgdp4 = _SGDP4(self.orbit_elements)

    def get_position(self, utc_time, normalize=True):
        """Get the cartesian position and velocity from the satellite.
        """

        kep, errors = self._sgdp4.propagate(utc_time)
        pos, vel = kep2xyz(kep)

        if normalize:
            pos /= XKMPER
            vel /= XKMPER * XMNPDA / SECDAY

        return pos, vel, errors

    def get_lonlatalt(self, utc_time):
        """Calculate sublon, sublat and altitude of satellite.
        http://celestrak.com/columns/v02n03/
        """
        (pos_x, pos_y, pos_z), (vel_x, vel_y, vel_z), errors = self.get_position(
            utc_time, normalize=True)

        lon = ((np.arctan2(pos_y * XKMPER, pos_x * XKMPER) - gmst(dt2np(utc_time)))
               % (2 * np.pi))

        lon = np.where(lon > np.pi, lon - np.pi * 2, lon)
        lon = np.where(lon <= -np.pi, lon + np.pi * 2, lon)

        r = np.sqrt(pos_x ** 2 + pos_y ** 2)
        lat = np.arctan2(pos_z, r)
        e2 = F * (2 - F)
        while True:
            lat2 = lat
            c = 1 / (np.sqrt(1 - e2 * (np.sin(lat2) ** 2)))
            lat = np.arctan2(pos_z + c * e2 * np.sin(lat2), r)
            if np.all(abs(lat - lat2) < 1e-10):
                break
        alt = r / np.cos(lat) - c
        alt *= A
        return np.rad2deg(lon), np.rad2deg(lat), alt, errors


# t1 = Tle("a", line1="1     5U 58002B   18231.96948527 -.00000019 +00000-0 -48070-4 0  9990", line2="2     5 034.2557 124.2521 1846373 229.0197 113.5561 10.84817833132766")
# t2 = Tle("b", line1="1    11U 59001A   18234.91021469 +.00000021 +00000-0 +14392-4 0  9993", line2="2    11 032.8682 030.1273 1466645 100.3180 276.5496 11.85533996196087")
# ts = np.array([t1,t2])

# o=OrbitElements(ts)

o = Orbitals([("1     5U 58002B   18231.96948527 -.00000019 +00000-0 -48070-4 0  9990",
               "2     5 034.2557 124.2521 1846373 229.0197 113.5561 10.84817833132766"),
              ("1    11U 59001A   18234.91021469 +.00000021 +00000-0 +14392-4 0  9993",
               "2    11 032.8682 030.1273 1466645 100.3180 276.5496 11.85533996196087")
              ])
