#!/usr/bin/env python

import inspect
import sys

class Utils(object):
    """common code for utils scripts
       Inherit from this in util classe, and then in main have either:

        a) if call is like script.py <env> <method> <args>
        env = sys.argv[1] if len(sys.argv)>1 else ''
        xxx = Xxx(env)._run(sys.argv, "env(e.g. mcpn1)")  # Xxx is class

        b) if call is like script.py <method> <args>
        xxx = Xxx()._run(sys.argv)  # Xxx is class

    """
    def __init__(self):
        pass

    def _help(self):
        """list all the functions"""

        for f in dir(self):
            if not f[0] == '_':
                func = getattr(self,f, None)
                if callable(func):
                    print("-------------")
                    print("function: {0}, args: {1}".format(f, inspect.signature(func)))
                    print("doc: {0}".format((getattr(self,f).__doc__ or ' ').splitlines()[0]))

    def _run(self, argv, pre_method_arg_text=''):
        """Run the method specified or give usage detail if invalid params
           argv is sys.argv passed from main
           the function name will either be argv[1] or or argv[2] (if pre_method_arg_text set)
           pre_method_arg_text is the text to display if argv[1] is invalid
        """
           
        method = None
        if pre_method_arg_text and len(argv)>2:
            method = argv[2]
            args = argv[3:]
        elif not pre_method_arg_text and len(argv)>1:
            method = argv[1]
            args = argv[2:]
        
        if method and getattr(self, method, None):
            ret = getattr(self, method)(*args)
            if ret is not None:
                if type(ret) is dict:
                    for i in ret:
                        print(i,ret[i])
                elif type(ret) is list:
                    for i in ret:
                        print(i)
                else:
                    print(ret)

        else:
            print("\nUsage:")
            print("{0} {1} <function name> <function args>\n".format(sys.argv[0],pre_method_arg_text))
            self._help()

