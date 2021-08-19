#!/usr/bin/env python

"""
Class and supporting code to hold all information on CCPP constituent
variables. A constituent variable is defined and maintained by the CCPP
Framework instead of the host model.
The ConstituentVarDict class contains methods to generate the necessary code
to implement this support.
"""

# Python library imports
from __future__ import print_function
import os
# CCPP framework imports
from file_utils import KINDS_MODULE
from fortran_tools import FortranWriter
from parse_tools import ParseInternalError
from metavar import Var, VarDictionary

########################################################################

CONST_DDT_NAME = "ccpp_model_constituents_t"
CONST_DDT_MOD = "ccpp_constituent_prop_mod"
CONST_PROP_TYPE = "ccpp_constituent_properties_t"

########################################################################

class ConstituentVarDict(VarDictionary):
    """A class to hold all the constituent variables for a CCPP Suite.
    Also contains methods to generate the necessary code for runtime
    allocation and support for these variables.
    """

    __const_prop_array_name  = "ccpp_constituent_array"
    __const_prop_init_name  = "ccpp_constituents_initialized"
    __const_prop_init_consts = "ccpp_create_constituent_array"
    __const_prop_type_name = "ccpp_constituent_properties_t"
    __constituent_type = "suite"

    def __init__(self, name, parent_dict, variables=None, logger=None):
        """Create a specialized VarDictionary for constituents.
        The main difference is functionality to allocate and support
        these variables with special functions for the host model.
        The main reason for a separate dictionary is that these are not
        proper Suite variables but will belong to the host model at run time.
        The <parent_dict> feature of the VarDictionary class is required
        because this dictionary must be connected to a host model.
        """
        super(ConstituentVarDict, self).__init__(name, variables=variables,
                                                 parent_dict=parent_dict,
                                                 logger=logger)

    def find_variable(self, standard_name=None, source_var=None,
                      any_scope=True, clone=None,
                      search_call_list=False, loop_subst=False):
        """Attempt to return the variable matching <standard_name>.
        if <standard_name> is None, the standard name from <source_var> is used.
        It is an error to pass both <standard_name> and <source_var> if
        the standard name of <source_var> is not the same as <standard_name>.
        If <any_scope> is True, search parent scopes if not in current scope.
        Note: Unlike the <VarDictionary> version of this method, the case for
              CCPP_CONSTANT_VARS is not handled -- it should have been handled
              by a lower level.
        If the variable is not found but is a constituent variable type,
           create the variable in this dictionary
        Note that although the <clone> argument is accepted for consistency,
           cloning is not handled at this level.
        If the variable is not found and <source_var> is not a constituent
           variable, return None.
        """
        if standard_name is None:
            if source_var is None:
                emsg = "One of <standard_name> or <source_var> must be passed."
                raise ParseInternalError(emsg)
            # end if
            standard_name = source_var.get_prop_value('standard_name')
        elif source_var is not None:
            stest = source_var.get_prop_value('standard_name')
            if stest != standard_name:
                emsg = ("Only one of <standard_name> or <source_var> may " +
                        "be passed.")
                raise ParseInternalError(emsg)
            # end if
        # end if
        if standard_name in self:
            var = self[standard_name]
        elif any_scope and (self._parent_dict is not None):
            srch_clist = search_call_list
            var = self._parent_dict.find_variable(standard_name=standard_name,
                                                  source_var=source_var,
                                                  any_scope=any_scope,
                                                  clone=None,
                                                  search_call_list=srch_clist,
                                                  loop_subst=loop_subst)
        else:
            var = None
        # end if
        if (var is None) and source_var and source_var.is_constituent():
            # If we did not find the variable and it is a constituent type,
            # add a clone of <source_var> to our dictionary.
            # First, maybe do a loop substitution
            dims = source_var.get_dimensions()
            newdims = list()
            for dim in dims:
                dstdnames = dim.split(':')
                new_dnames = list()
                for dstdname in dstdnames:
                    if dstdname == 'horizontal_loop_extent':
                        new_dnames.append('horizontal_dimension')
                    elif dstdname == 'horizontal_loop_end':
                        new_dnames.append('horizontal_dimension')
                    elif dstdname == 'horizontal_loop_begin':
                        new_dnames.append('ccpp_constant_one')
                    else:
                        new_dnames.append(dstdname)
                    # end if
                # end for
                newdims.append(':'.join(new_dnames))
            # end for
            var = source_var.clone({'dimensions' : newdims}, remove_intent=True,
                                   source_type=self.__constituent_type)
            self.add_variable(var)
        return var

    def declare_public_interfaces(self, outfile, indent):
        """Declare the public constituent interfaces.
        Declarations are written to <outfile> at indent, <indent>."""
        outfile.write("! Public interfaces for handling constituents", indent)
        outfile.write("! Return the number of constituents for this suite",
                      indent)
        outfile.write("public :: {}".format(self.num_consts_funcname()), indent)
        outfile.write("! Return the name of a constituent", indent)
        outfile.write("public :: {}".format(self.const_name_subname()), indent)
        outfile.write("! Copy the data for a constituent", indent)
        outfile.write("public :: {}".format(self.copy_const_subname()), indent)

    def declare_private_data(self, outfile, indent):
        """Declare private suite module variables and interfaces
        to <outfile> with indent, <indent>."""
        outfile.write("! Private constituent module data", indent)
        if self:
            stmt = "type({}), private, allocatable :: {}(:)"
            outfile.write(stmt.format(self.constituent_prop_type_name(),
                                      self.constituent_prop_array_name()),
                          indent)
        # end if
        stmt = "logical, private :: {} = .false."
        outfile.write(stmt.format(self.constituent_prop_init_name()), indent)
        outfile.write("! Private interface for constituents", indent)
        stmt = "private :: {}"
        outfile.write(stmt.format(self.constituent_prop_init_consts()), indent)

    def _write_init_check(self, outfile, indent, suite_name,
                          errvar_names, use_errflg):
        """Write a check to <outfile> to make sure the constituent properties
        are initialized. Write code to initialize the error variables and/or
        set them to error values."""
        outfile.write('', 0)
        if use_errflg:
            outfile.write("errflg = 0", indent+1)
            outfile.write("errmsg = ''", indent+1)
        else:
            raise ParseInternalError("Alternative to errflg not implemented")
        # end if
        outfile.write("! Make sure that our constituent array is initialized",
                      indent+1)
        stmt = "if (.not. {}) then"
        outfile.write(stmt.format(self.constituent_prop_init_name()), indent+1)
        if use_errflg:
            outfile.write("errflg = 1", indent+2)
            stmt = 'errmsg = "constituent properties not '
            stmt += 'initialized for suite, {}"'
            outfile.write(stmt.format(suite_name), indent+2)
            outfile.write("end if", indent+1)
        # end if (no else until an alternative error mechanism supported)

    def _write_index_check(self, outfile, indent, suite_name,
                           errvar_names, use_errflg):
        """Write a check to <outfile> to make sure the "index" input
        is in bounds. Write code to set error variables if index is
        out of bounds."""
        if use_errflg:
            if self:
                outfile.write("if (index < 1) then", indent+1)
                outfile.write("errflg = 1", indent+2)
                stmt = "write(errmsg, '(a,i0,a)') 'ERROR: index (',index,') "
                stmt += "too small, must be >= 1'"
                outfile.write(stmt, indent+2)
                stmt = "else if (index > SIZE({})) then"
                outfile.write(stmt.format(self.constituent_prop_array_name()),
                              indent+1)
                outfile.write("errflg = 1", indent+2)
                stmt = "write(errmsg, '(2(a,i0))') 'ERROR: index (',index,') "
                stmt += "too large, must be <= ', SIZE({})"
                outfile.write(stmt.format(self.constituent_prop_array_name()),
                              indent+2)
                outfile.write("end if", indent+1)
            else:
                outfile.write("errflg = 1", indent+1)
                stmt = "write(errmsg, '(a,i0,a)') 'ERROR: suite, {}, "
                stmt += "has no constituents'"
                outfile.write(stmt, indent+1)
            # end if
        else:
            raise ParseInternalError("Alternative to errflg not implemented")
        # end if

    def write_constituent_routines(self, outfile, indent, suite_name, err_vars):
        """Write the subroutine that, when called allocates and defines the
        suite-cap module variable describing the constituent species for
        this suite.
        Code is written to <outfile> starting at indent, <indent>."""
        # Format our error variables
        errvar_names = [x.get_prop_value('local_name') for x in err_vars]
        use_errflg = ('errflg' in errvar_names) and ('errmsg' in errvar_names)
        errvar_alist = ", ".join([x for x in errvar_names])
        errvar_alist2 = ", {}".format(errvar_alist) if errvar_alist else ""
        errvar_call = ", ".join(["{}={}".format(x,x) for x in errvar_names])
        errvar_call2 = ", {}".format(errvar_call) if errvar_call else ""
        # Allocate and define constituents
        stmt = "subroutine {}({})".format(self.constituent_prop_init_consts(),
                                          errvar_alist)
        outfile.write(stmt, indent)
        outfile.write("! Allocate and fill the constituent property array",
                      indent + 1)
        outfile.write("!    for this suite", indent+1)
        outfile.write("! Dummy arguments", indent+1)
        for evar in err_vars:
            evar.write_def(outfile, indent+1, self, dummy=True)
        # end for
        if self:
            outfile.write("! Local variables", indent+1)
            outfile.write("integer :: index", indent+1)
            stmt = "allocate({}({}))"
            outfile.write(stmt.format(self.constituent_prop_array_name(),
                                      len(self)), indent+1)
            outfile.write("index = 0", indent+1)
        # end if
        for std_name, var in self.items():
            outfile.write("index = index + 1", indent+1)
            dims = var.get_dim_stdnames()
            if 'vertical_layer_dimension' in dims:
                vertical_dim = 'vertical_layer_dimension'
            elif 'vertical_interface_dimension' in dims:
                vertical_dim = 'vertical_interface_dimension'
            else:
                vertical_dim = ''
            # end if
            advect_str = self.TF_string(var.get_prop_value('advected'))
            stmt = 'call {}(index)%initialize("{}", "{}", {}{})'
            outfile.write(stmt.format(self.constituent_prop_array_name(),
                                      std_name, vertical_dim, advect_str,
                                      errvar_call2), indent+1)
        # end for
        outfile.write("{} = .true.".format(self.constituent_prop_init_name()),
                      indent+1)
        stmt = "end subroutine {}".format(self.constituent_prop_init_consts())
        outfile.write(stmt, indent)
        outfile.write("", 0)
        outfile.write("\n! {}\n".format("="*72), 1)
        # Return number of constituents
        fname = self.num_consts_funcname()
        outfile.write("integer function {}({})".format(fname, errvar_alist),
                      indent)
        outfile.write("! Return the number of constituents for this suite",
                      indent+1)
        outfile.write("! Dummy arguments", indent+1)
        for evar in err_vars:
            evar.write_def(outfile, indent+1, self, dummy=True)
        # end for
        outfile.write("! Make sure that our constituent array is initialized",
                      indent+1)
        stmt = "if (.not. {}) then"
        outfile.write(stmt.format(self.constituent_prop_init_name()), indent+1)
        outfile.write("call {}({})".format(self.constituent_prop_init_consts(),
                                           errvar_call), indent+2)
        outfile.write("end if", indent+1)
        outfile.write("{} = {}".format(fname, len(self)), indent+1)
        outfile.write("end function {}".format(fname), indent)
        outfile.write("\n! {}\n".format("="*72), 1)
        # Return the name of a constituent given an index
        stmt = "subroutine {}(index, name_out{})"
        outfile.write(stmt.format(self.const_name_subname(), errvar_alist2),
                      indent)
        outfile.write("! Return the name of constituent, <index>", indent+1)
        outfile.write("! Dummy arguments", indent+1)
        outfile.write("integer,            intent(in)    :: index", indent+1)
        outfile.write("character(len=*),   intent(out)   :: name_out", indent+1)
        for evar in err_vars:
            evar.write_def(outfile, indent+1, self, dummy=True)
        # end for
        self._write_init_check(outfile, indent, suite_name,
                               errvar_names, use_errflg)
        self._write_index_check(outfile, indent, suite_name,
                                errvar_names, use_errflg)
        if self:
            stmt = "call {}(index)%standard_name(name_out{})"
            outfile.write(stmt.format(self.constituent_prop_array_name(),
                                      errvar_call2), indent+1)
        # end if
        outfile.write("end subroutine {}".format(self.const_name_subname()),
                      indent)
        outfile.write("\n! {}\n".format("="*72), 1)
        # Copy a consitituent's properties
        stmt = "subroutine {}(index, cnst_out{})"
        fname = self.copy_const_subname()
        outfile.write(stmt.format(fname, errvar_alist2), indent)
        outfile.write("! Copy the data for a constituent", indent+1)
        outfile.write("! Dummy arguments", indent+1)
        outfile.write("integer,            intent(in)    :: index", indent+1)
        stmt = "type({}), intent(out)     :: cnst_out"
        outfile.write(stmt.format(self.constituent_prop_type_name()), indent+1)
        for evar in err_vars:
            evar.write_def(outfile, indent+1, self, dummy=True)
        # end for
        self._write_init_check(outfile, indent, suite_name,
                               errvar_names, use_errflg)
        self._write_index_check(outfile, indent, suite_name,
                                errvar_names, use_errflg)
        if self:
            stmt = "cnst_out = {}(index)"
            outfile.write(stmt.format(self.constituent_prop_array_name()),
                          indent+1)
        # end if
        outfile.write("end subroutine {}".format(fname), indent)

    def constituent_module_name(self):
        """Return the name of host model constituent module"""
        if not ((self.parent is not None) and
                hasattr(self.parent.parent, "constituent_module")):
            emsg = "ConstituentVarDict parent not HostModel?"
            emsg += "\nparent is '{}'".format(type(self.parent.parent))
            raise ParseInternalError(emsg)
        # end if
        return self.parent.parent.constituent_module

    def num_consts_funcname(self):
        """Return the name of the function which returns the number of
        constituents for this suite."""
        return "{}_num_consts".format(self.name)

    def const_name_subname(self):
        """Return the name of the routine that returns a constituent's
           given an index"""
        return "{}_const_name".format(self.name)

    def copy_const_subname(self):
        """Return the name of the routine that returns a copy of a
           constituent's metadata given an index"""
        return "{}_copy_const".format(self.name)

    @staticmethod
    def constituent_index_name(standard_name):
        """Return the index name associated with <standard_name>"""
        return "index_of_{}".format(standard_name)

    @staticmethod
    def write_constituent_use_statements(cap, suite_list, indent):
        """Write the suite use statements needed by the constituent
        initialization routines."""
        maxmod = max([len(s.module) for s in suite_list])
        smod = len(CONST_DDT_MOD)
        maxmod = max(maxmod, smod)
        use_str = "use {},{} only: {}"
        spc = ' '*(maxmod - smod)
        cap.write(use_str.format(CONST_DDT_MOD, spc, CONST_PROP_TYPE), indent)
        cap.write('! Suite constituent interfaces', indent)
        for suite in suite_list:
            const_dict = suite.constituent_dictionary()
            smod = suite.module
            spc = ' '*(maxmod - len(smod))
            fname = const_dict.num_consts_funcname()
            cap.write(use_str.format(smod, spc, fname), indent)
            fname = const_dict.const_name_subname()
            cap.write(use_str.format(smod, spc, fname), indent)
            fname = const_dict.copy_const_subname()
            cap.write(use_str.format(smod, spc, fname), indent)
        # end for

    @staticmethod
    def write_host_routines(cap, host, reg_funcname, num_const_funcname,
                            copy_in_funcname, copy_out_funcname, const_obj_name,
                            const_names_name, const_indices_name,
                            suite_list, err_vars):
        """Write out the host model <reg_funcname> routine which will
        instantiate constituent fields for all the constituents in <suite_list>.
        <err_vars> is a list of the host model's error variables.
        Also write out the following routines:
           <num_const_funcname>: Number of constituents
           <copy_in_funcname>: Collect constituent fields for host
           <copy_out_funcname>: Update constituent fields from host
        Output is written to <cap>.
        """
# XXgoldyXX: v need to generalize host model error var type support
        err_callstr = "errflg=errflg, errmsg=errmsg"
# XXgoldyXX: ^ need to generalize host model error var type support
        err_names = [x.get_prop_value('local_name') for x in err_vars]
        errvar_str = ', '.join(err_names)
        # First up, the registration routine
        substmt = "subroutine {}".format(reg_funcname)
        stmt = "{}(suite_list, ncols, num_layers, num_interfaces, {})"
        stmt = stmt.format(substmt, errvar_str)
        cap.write(stmt, 1)
        cap.write("! Create constituent object for suites in <suite_list>", 2)
        cap.write("", 0)
        ConstituentVarDict.write_constituent_use_statements(cap, suite_list, 2)
        cap.write("", 0)
        cap.write("! Dummy arguments", 2)
        cap.write("character(len=*),   intent(in)    :: suite_list(:)", 2)
        cap.write("integer,            intent(in)    :: ncols", 2)
        cap.write("integer,            intent(in)    :: num_layers", 2)
        cap.write("integer,            intent(in)    :: num_interfaces", 2)
        for evar in err_vars:
            evar.write_def(cap, 2, host, dummy=True, add_intent="out")
        # end for
        cap.write("! Local variables", 2)
        spc = ' '*37
        cap.write("integer{} :: num_suite_consts".format(spc), 2)
        cap.write("integer{} :: num_consts".format(spc), 2)
        cap.write("integer{} :: index".format(spc), 2)
        cap.write("integer{} :: field_ind".format(spc), 2)
        cap.write("type({}), pointer :: const_prop".format(CONST_PROP_TYPE), 2)
        cap.write("", 0)
        cap.write("num_consts = 0", 2)
        for suite in suite_list:
            const_dict = suite.constituent_dictionary()
            funcname = const_dict.num_consts_funcname()
            cap.write("! Number of suite constants for {}".format(suite.name),
                      2)
            cap.write("num_suite_consts = {}({})".format(funcname,
                                                         errvar_str), 2)
            cap.write("num_consts = num_consts + num_suite_consts", 2)
        # end for
        cap.write("if (errflg == 0) then", 2)
        cap.write("! Initialize constituent data and field object", 3)
        stmt = "call {}%initialize_table(num_consts)"
        cap.write(stmt.format(const_obj_name), 3)
        cap.write("end if", 2)
        for suite in suite_list:
            cap.write("if (errflg == 0) then", 2)
            cap.write("! Add {} constituent metadata".format(suite.name), 3)
            const_dict = suite.constituent_dictionary()
            funcname = const_dict.num_consts_funcname()
            cap.write("num_suite_consts = {}({})".format(funcname,
                                                         errvar_str), 3)
            cap.write("end if", 2)
            funcname = const_dict.copy_const_subname()
            cap.write("do index = 1, num_suite_consts", 2)
            cap.write("allocate(const_prop, stat=errflg)", 3)
            cap.write("if (errflg /= 0) then", 3)
            cap.write('errmsg = "ERROR allocating const_prop"', 4)
            cap.write("end if", 3)
            cap.write("if (errflg == 0) then", 3)
            stmt = "call {}(index, const_prop, {})"
            cap.write(stmt.format(funcname, err_callstr), 4)
            cap.write("end if", 3)
            cap.write("if (errflg == 0) then", 3)
            stmt = "call {}%new_field(const_prop, {})"
            cap.write(stmt.format(const_obj_name, err_callstr), 4)
            cap.write("end if", 3)
            cap.write("nullify(const_prop)", 3)
            cap.write("if (errflg /= 0) then", 3)
            cap.write("exit", 4)
            cap.write("end if", 3)
            cap.write("end do", 2)
            cap.write("", 0)
        # end for
        cap.write("if (errflg == 0) then", 2)
        stmt = "call {}%lock_table(ncols, num_layers, num_interfaces, {})"
        cap.write(stmt.format(const_obj_name, err_callstr), 3)
        cap.write("end if", 2)
        cap.write("! Set the index for each active constituent", 2)
        cap.write("do index = 1, SIZE({})".format(const_indices_name), 2)
        stmt = "field_ind = {}%field_index({}(index), {})"
        cap.write(stmt.format(const_obj_name, const_names_name, err_callstr), 3)
        cap.write("if (field_ind > 0) then", 3)
        cap.write("{}(index) = field_ind".format(const_indices_name), 4)
        cap.write("else", 3)
        cap.write("errflg = 1", 4)
        stmt = "errmsg = 'No field index for '//trim({}(index))"
        cap.write(stmt.format(const_names_name), 4)
        cap.write("end if", 3)
        cap.write("if (errflg /= 0) then", 3)
        cap.write("exit", 4)
        cap.write("end if", 3)
        cap.write("end do", 2)
        cap.write("end {}".format(substmt), 1)
        # Next, write num_consts routine
        substmt = "function {}".format(num_const_funcname)
        cap.write("", 0)
        cap.write("integer {}({})".format(substmt, errvar_str), 1)
        cap.write("! Return the number of constituent fields for this run", 2)
        cap.write("", 0)
        cap.write("! Dummy arguments", 2)
        for evar in err_vars:
            evar.write_def(cap, 2, host, dummy=True, add_intent="out")
        # end for
        cap.write("", 0)
        cap.write("{} = {}%num_constituents({})".format(num_const_funcname,
                                                        const_obj_name,
                                                        err_callstr), 2)
        cap.write("end {}".format(substmt), 1)
        # Next, write copy_in routine
        substmt = "subroutine {}".format(copy_in_funcname)
        cap.write("", 0)
        cap.write("{}(const_array, {})".format(substmt, errvar_str), 1)
        cap.write("! Copy constituent field info into <const_array>", 2)
        cap.write("", 0)
        cap.write("! Dummy arguments", 2)
        cap.write("real(kind_phys),    intent(out)   :: const_array(:,:,:)", 2)
        for evar in err_vars:
            evar.write_def(cap, 2, host, dummy=True, add_intent="out")
        # end for
        cap.write("", 0)
        cap.write("call {}%copy_in(const_array, {})".format(const_obj_name,
                                                            err_callstr), 2)
        cap.write("end {}".format(substmt), 1)
        # Next, write copy_out routine
        substmt = "subroutine {}".format(copy_out_funcname)
        cap.write("", 0)
        cap.write("{}(const_array, {})".format(substmt, errvar_str), 1)
        cap.write("! Update constituent field info from <const_array>", 2)
        cap.write("", 0)
        cap.write("! Dummy arguments", 2)
        cap.write("real(kind_phys),    intent(in)    :: const_array(:,:,:)", 2)
        for evar in err_vars:
            evar.write_def(cap, 2, host, dummy=True, add_intent="out")
        # end for
        cap.write("", 0)
        cap.write("call {}%copy_out(const_array, {})".format(const_obj_name,
                                                             err_callstr), 2)
        cap.write("end {}".format(substmt), 1)

    @staticmethod
    def constitutent_source_type():
        """Return the source type for constituent species"""
        return ConstituentVarDict.__constituent_type

    @staticmethod
    def constituent_prop_array_name():
        """Return the name of the constituent properties array for this suite"""
        return ConstituentVarDict.__const_prop_array_name

    @staticmethod
    def constituent_prop_init_name():
        """Return the name of the array initialized flag for this suite"""
        return ConstituentVarDict.__const_prop_init_name

    @staticmethod
    def constituent_prop_init_consts():
        """Return the name of the routine to initialize the constituent
        properties array for this suite"""
        return ConstituentVarDict.__const_prop_init_consts

    @staticmethod
    def constituent_prop_type_name():
        """Return the name of the derived type which holds constituent
        properties."""
        return ConstituentVarDict.__const_prop_type_name

    @staticmethod
    def write_suite_use(outfile, indent):
        """Write use statements for any modules needed by the suite cap.
        The statements are written to <outfile> at indent, <indent>.
        """
        omsg = "use ccpp_constituent_prop_mod, only: {}"
        cpt_name = ConstituentVarDict.constituent_prop_type_name()
        outfile.write(omsg.format(cpt_name), indent)

    @staticmethod
    def TF_string(tf_val):
        """Return a string of the Fortran equivalent of <tf_val>"""
        if tf_val:
            tf_str = ".true."
        else:
            tf_str = ".false."
        # end if
        return tf_str
