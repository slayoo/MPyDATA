import numpy as np


class SizeDistribution:
    def __init__(self, si):
        self.si = si
        
    def cdf(self, r):
        return (
                175 * np.sqrt(2 * np.pi / 11) *
                np.erf(np.sqrt(22) * np.log(r / (7 * self.si.micrometre)) / np.log(10)) *
                np.log(10) *
                (1 / self.si.centimetre ** 3)
        )
    
    def pdf(self, r):
        return (
                (700 * self.si.micrometre) / r *
                np.exp(-22 * (np.log10(r / (7 * self.si.micrometre)) ** 2)) *
                (1 / self.si.centimetre ** 3 / self.si.micrometre))

