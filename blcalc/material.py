"""
Material, represents a single soil material,
assume every soil is saturated for now
"""
import copy

def _group_index_correction(group_index):
    """
    The input group_index may not contain proper group_index as required by problem
    Fix it,
    Like L was found in various logs as I
    """
    if len(group_index)==1:
        #just to make sure 2 letter group_index is available
        group_index=group_index+group_index
    if group_index[1]=='I':
        #Is I for intermediate[not standard] or is it actually L
        group_index=group_index[0]+'L'
    if not group_index[0] in ['S','M','G','C','P','O']:
        group_index=group_index[1]+group_index[1]
    if not group_index[0] in ['S','M','G','C','P','O']:
        #cannot determine make it clay
        #@TODO add fail here
        group_index='C'+group_index[1]
    return group_index

# _clamp result between min and max values
def _clamp(value, amin, amax):
    if value<amin:
        return amin
    if value>amax:
        return amax
    return value

class Material:
    """
    It is a single soil material for a layer,
    it takes SPT and other previously known material properties,
    and group_indexves the unknown by analytical formulas,
    this contains datas like surchage too
    """
    def is_clayey(self):
        """
        Check first letter and determine if soil is clayey
        """
        group_index = self._data['GI']
        return group_index[1] not in ['S','G']

    def _get_n(self):
        """
        Get n_60 value
        No overburden is applied since we have shallow depth(more errors)
        - Dilitarcy correction is applied for sand
        """#@Needs to fix it for general case
        n_60 = 0.55 * 1 * 1 * 0.75 * self._data['spt'] /0.6
        if not self.is_clayey() and n_60>15: #apply dilitracy correction
            n_60 = 15 + 0.5 * (n_60 - 15)
        return n_60

    def _get_gamma(self):
        """
        Get value of gamma based on soil type
        """
        gamma = None
        if self.is_clayey():
            gamma = 16.8 + 0.15*self._data['n60']
        else:
            gamma = 16 + 0.1 * self._data['n60']
        gamma=_clamp(gamma,10,2.8*9.81)#do we need this
        return gamma

    # Note: The unconfined compressive strength value is two times undrained shear strength. The
    # ultimate bearing capacity is approximately six times the undrained shear strength where C in
    # CNc is the undrained shear strength. The value of Nc is 5.14 and 5.7 respectively by
    # Meyerhof and Terzaghi.
    # BC Mapping Bhadra 4

    @staticmethod
    def qu(N60):
        """
        Determine Qu from N60
        """
        return 0.29 * N60**0.72 * 100

    # correction from: https://civilengroup_indexneeringbible.com/subtopics.php?i=91
    def _get_cu(self):
        """
        Get cohesion of soil
        """
        c_undrained=0
        group_index = self._data['GI']
        if self.is_clayey():
            c_undrained = self.qu(self._data['n60'])/2
            #c_undrained=_clamp(c_undrained, 10, 103)
        if group_index in ('CG', 'GC'):
            c_undrained=_clamp(c_undrained, 20, 25)
        elif group_index == 'SM':
            c_undrained=_clamp(c_undrained,20,50)
        elif group_index == 'SC':
            c_undrained=_clamp(c_undrained,5,75)
        #fix based on packing state, something is wrong here
        packing_case = self._data['_pc']
        if packing_case==1:
            c_undrained=_clamp(c_undrained,0.21,25)
        elif packing_case==2:
            c_undrained=_clamp(c_undrained,25,80)
        elif packing_case==3:
            c_undrained=_clamp(c_undrained,80,150)
        elif packing_case==4:
            c_undrained=_clamp(c_undrained,150,400)
        # Plasix calculation needs very small c_undrained
        _clamp(c_undrained,0.21,1e8)#use 0.2 as per plasix recommendation
        return c_undrained#the cu is always 103 check with small value of n_60, some mistake maybe

    def _get_packing_state(self):
        """
        Get packing state table column
        """
        # Ok, first determining packing condition as per Table 2.4,
        s_phelp = [0,4,10,30,50]
        if self.is_clayey():
            s_phelp = [0,2,4,8,15,30]
        packing_case = 0 # Packing cases as per table
        for i,value in enumerate(s_phelp):
            if self._data['n60']>value:
                packing_case=i
        return packing_case

    @staticmethod
    def phi(N60):
        """
        Determine phi from N60
        """
        return 27.1 + 0.3*N60 - 0.00054* N60**2

    def _get_phi(self):
        """
        Get phi of soil
        #Many tables are used need to be refactred
        """
        phi = self.phi(self._data['n60'])
        group_index = self._data['GI']
        packing_case = self._data['_pc']
        if group_index[0]=='G':
            if group_index[1]=='W':
                phi=_clamp(phi, 33, 40)
            else:
                phi=_clamp(phi, 32, 44)
        elif group_index[0]=='S':
            if packing_case<=1:
                phi = _clamp(phi,20,35)
            elif packing_case==2:
                phi = _clamp(phi,25,40)
            elif packing_case==3:
                phi = _clamp(phi,30,45)
            elif packing_case==4:
                phi = _clamp(phi,35,45)
            else:
                phi = _clamp(phi,40,60)
        elif group_index[0]=='C':
            if group_index[1]=='H':
                phi = _clamp(phi, 17, 31)
            else:
                phi = _clamp(phi, 27, 35)
        else:
            phi = _clamp(phi, 23, 41)
        ### Ok that was according to table but let's remove for clay
        if self.is_clayey():
            phi=0.01 #very small value for plasix
        return phi

    def _get_e(self):
        """
        Elasticity
        """
        group_index = self._data['GI']
        n_60 = self._data['n60']
        packing_case = self._data['_pc']

        elasticity=None
        if self.is_clayey():
            if packing_case==0:#15-40
                elasticity= (15+40)/2 * n_60 * 100
            elif packing_case==1:#40-80
                elasticity= (40+80)/2 * n_60 * 100
            else:#80-200
                elasticity= (80+200)/2 * n_60 * 100
        else:
            if group_index[1] in ['M','C','P','O']:#with fines
                elasticity= 5 * n_60 * 100
            else: #The OCR condition of cohesionless test cannot be determined, assume NC sand
                elasticity= 10 * n_60 * 100
        # Now check value ranges
        """
        if group_index[0] == 'S':
            if group_index[1] == 'M':
                elasticity=_clamp(elasticity, 10_000, 20_000)
            if packing_case<=2:
                elasticity=_clamp(elasticity, 2_000, 25_000)
            elif packing_case==3:
                elasticity=_clamp(elasticity, 15_000, 30_000)
            else:
                elasticity=_clamp(elasticity, 35_000, 55_000)
            elasticity= _clamp(elasticity, 2_000, 55_000)
        elif group_index[0] == 'G':
            elasticity=_clamp(elasticity,70_000,170_000)
        elif group_index[0]=='C':
            if packing_case<=2:
                elasticity=_clamp(elasticity,2_000, 20_000)
            elif packing_case<=4:
                elasticity=_clamp(elasticity,20_000, 40_000)
            else:
                elasticity=_clamp(elasticity,40_000,100_000)
        elif group_index[0]=='M':
            elasticity=_clamp(elasticity,4_000,30_000)
        else:#min both
            if packing_case<=2:
                elasticity=_clamp(elasticity, 2_000, 20_000)
            else:
                elasticity=_clamp(elasticity, 10_000, 55_000)
        """#remove clamp now
        return elasticity

    def __init__(self, input_data):
        """
        Save only use later when required
        """
        self._data = input_data
        self._data['GI'] = _group_index_correction(self._data['GI'])
        if 'n60' not in self._data:
            self._data['n60'] = self._get_n()
        if '_pc' not in self._data:
            self._data['_pc'] = self._get_packing_state()
        if 'gamma' not in self._data:
            self._data['gamma'] = self._get_gamma()
        if 'cu' not in self._data:
            self._data['cu'] = self._get_cu()
        if 'phi' not in self._data:
            self._data['phi'] = self._get_phi()
        if 'e' not in self._data:
            self._data['e'] = self._get_e()
        if 'nu' not in self._data:
            if self.is_clayey():
                self._data['nu'] = 0.5
            else:
                self._data['nu'] = 0.3

    def get(self):
        """
        display material as as object
        """
        return self._data

class LayerSoil:
    """
    Use to determine multiple layer of soil
    so include surchage info also
    """
    def __init__(self, data):
        self._data = data
        self._values = []
        prev_surchage = 0.
        prev_depth = 0.
        for layer in data:
            layer['q'] = prev_surchage
            mat = Material(layer)
            res = mat.get()
            new_depth = res['depth']
            prev_surchage += res['gamma']*(new_depth-prev_depth)
            prev_depth=new_depth
            self._values.append(res)

    def get(self, depth=None):
        """
        Return soil material at givel depth
        if no depth is given returns all saved materials
        """
        if depth is None:#Return all
            return self._values

        if depth<self._values[0]['depth']:
            mat = copy.copy(self._values[0])
            mat['depth']=depth
            mat['q']=mat['gamma']*depth
            return mat
        row=0
        while self._values[row]['depth']<depth:
            row+=1
        mat = copy.copy(self._values[row])
        mat['q']= mat['q'] - self._values[row-1]['gamma']*(mat['depth']-depth)
        mat['depth']=depth
        return mat

if __name__ == "__main__":
    import doctest
    doctest.testmod()
