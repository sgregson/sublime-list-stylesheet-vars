import sublime, sublime_plugin, os, re

def debug(content):
  if True:
    print(content)

class StyleSheetSetup:
    def __init__(self, extensions, regex, partials=None, index=None):
        if partials is None:
            self.partials = False
        else:
            self.partials = partials

        if index is None:
            self.index = False
        else:
            self.index = index

        self.extensions = extensions
        self.regex = regex

class ListStylesheetVariables(sublime_plugin.TextCommand):
    def run(self, edit):
        settings = sublime.load_settings('stylevariables.sublime-settings')

        handle_imports = settings.get("readImported")
        read_all_views = settings.get("readAllViews")
        self.read_parents   = settings.get("readParents")

        # Define setups
        less_setup = StyleSheetSetup((b'.less', b'.lessimport'), "(@[^\s\\]]*)\s*: *(.*);")
        sass_setup = StyleSheetSetup((b'.sass', b'.scss', b'.css.scss'), "^\s*(\$[^\s\\]{}]*)\s*: *([^;\n]*);?", True) # Last argument True because using partials
        stylus_setup = StyleSheetSetup((b'.styl',), "^\s*([^\s\\]\[]*) *= *([^;\n]*)", False, True)
        sass_erb_setup = StyleSheetSetup((b'.scss.erb', b'.sass.erb'), "^\s*(\$[^\s\\]{}]*)\s*: <?%?=? *([^;\n]*);? [\%>]?", True)

        # Add all setups to the setup tuple
        setups = (less_setup, sass_setup, stylus_setup, sass_erb_setup)

        chosen_setup = None

        self.edit = edit
        fn = self.view.file_name().encode("utf-8")

        for setup in setups:
            for ext in setup.extensions:
                if fn.endswith(ext):
                    chosen_setup = setup

        if chosen_setup == None:
            return

        # ----------------------------------------------------
        # FIND VARIABLES RECURSIVELY THROUGH THE @IMPORT CHAIN
        imported_vars = []
        if handle_imports:
            self.view.find_all("@import [\"|\'](.*)[\"|\']", 0, "$1", imported_vars)
            imported_vars = self.get_imports(self.view.file_name(), imported_vars, chosen_setup)

            # -------------------------------
            # FOUND NO VARIABLES, DISPLAY ALL
            if len(imported_vars) == 0:
                splitpath = os.path.split(self.view.file_name())
                splitpath = splitpath[0].split('\\')
                for i,seg in enumerate(splitpath):
                    if seg == "partials":
                        variablesPath = '/'.join(splitpath[0:i+1]) + '/variables/'
                        allVarFiles = [ f for f in os.listdir(variablesPath) if os.path.isfile(os.path.join(variablesPath,f)) ]
                        imported_vars = self.get_imports(variablesPath, allVarFiles, chosen_setup)
                        break;


        self.variables = []
        vars_from_views = []

        if read_all_views:
            for view in self.view.window().views():
                viewfn = self.view.file_name().encode("utf-8")
                compatible_view = False

                for ext in chosen_setup.extensions:
                    if viewfn.endswith(ext):
                        viewvars = []
                        view.find_all(chosen_setup.regex, 0, "$1|$2", viewvars)
                        vars_from_views += viewvars
                        break;
        else:
            self.view.find_all(chosen_setup.regex, 0, "$1|$2", self.variables)
            viewfn = re.sub("(_var_)|(_global_)","", os.path.split(self.view.file_name())[1].split('.')[0]);
            for i,val in enumerate(self.variables):
                self.variables[i] += "|" + viewfn;



        self.variables += vars_from_views
        self.variables = list(set(self.variables))
        for i, val in enumerate(self.variables):
            self.variables[i] = val.split("|")
        self.variables = imported_vars + self.variables

        # Make Unique and Sort
        self.variables = [list(x) for x in set(tuple(x) for x in self.variables)]
        self.variables.sort()

        debug(self.variables)
        #Determine maxlength for right-alignment
        maxlen = [0,0,0]    #[name,value,file]
        for i, val in enumerate(self.variables):
            self.variables[i][1] = re.sub("!default","!d", val[1])
            debug(self.variables[i])
            if len(val[0]) > maxlen[0]:
                maxlen[0] = len(val[0])
            if len(val[1]) > maxlen[1]:
                maxlen[1] = len(val[1])
            if len(val[2]) > maxlen[2]:
                maxlen[2] = len(val[2])

        # Create Quick Panel Layout
        for ndx, val in enumerate(self.variables):
            rep = (maxlen[0] - len(val[0]), maxlen[1] - len(val[1]), maxlen[2] - len(val[2]))
            # for subtext, use self.variables[ndx] = [main,subtext]
            self.variables[ndx] = str(val[0] + (" " * rep[0]) + " [" + val[1] + "]  " + (" " * (rep[1]+rep[2])) + val[2])

        self.view.window().show_quick_panel(self.variables, self.insert_variable, sublime.MONOSPACE_FONT)

    def insert_variable(self, choice):
        if choice == -1:
            return
        else:
            target = self.variables[choice] #[0] #if subtext option

        insertion = target.split(" [")
        self.view.run_command('insert_text', {'string': insertion[0].strip()})


    def get_imports(self, fn, imports, chosen_setup):
        # Handle imports
        imported_vars = []

        compiled_regex = re.compile(chosen_setup.regex, re.MULTILINE)

        file_dir = os.path.dirname(fn)

        for i, filename in enumerate(imports):
            has_extension = False

            for ext in chosen_setup.extensions:
                if filename.endswith(ext.decode("utf-8")):
                    has_extension = True

            if has_extension == False:
                # We need to try and find the right extension
                for ext in chosen_setup.extensions:
                    ext = ext.decode("utf-8")

                    # just adding the extension at the end
                    if os.path.isfile(os.path.normpath(file_dir + '/' + filename + ext)):
                        filename += ext
                        break

                    if chosen_setup.partials:
                        fn_split = os.path.split(filename)
                        partial_filename = fn_split[0] + "/_" + fn_split[1]
                        # above + adding an _ before the filename (partials)
                        if os.path.isfile(os.path.normpath(file_dir +  partial_filename + ext)):
                            filename = partial_filename + ext
                            break
                        # above plus adding a / at the beginning (relative paths)
                        if os.path.isfile(os.path.normpath(file_dir + "/" + partial_filename + ext)):
                            filename = partial_filename + ext
                            break
                    if chosen_setup.index and os.path.isfile(os.path.normpath(file_dir + "/" + filename + "/index" + ext)):
                        filename += "/index" + ext
                        break
            try:
                f = open(os.path.normpath(file_dir + '/' + filename), 'r')
                contents = f.read()
                f.close()

                m = re.findall(compiled_regex, contents)
                # Add Filename to tuple
                for i,myVars in enumerate(m):
                    m[i] = myVars + ("@" + re.sub("(_var_)|(_global_)","",os.path.split(filename)[1].split('.')[0]),)

                imported_vars = imported_vars + m

                # recursively find ancestor import statements
                if self.read_parents:
                    grandparents = re.findall("(?<=@import [\"|\'])(.*)(?=[\"|\'])", contents)
                    if len(grandparents) > 0:
                        # print grandparents
                        for i, gp_name in enumerate(grandparents):
                            imported_vars = imported_vars + self.get_imports(os.path.normpath(file_dir + '/' + filename), grandparents, chosen_setup)
            except:
                print('Could not load file ' + os.path.normpath(file_dir + '/' + filename) + ' from: ' + fn)


        # Convert a list of tuples to a list of lists
        imported_vars = [list(item) for item in imported_vars]

        return imported_vars

class InsertText(sublime_plugin.TextCommand):
    def run(self, edit, string=''):
        for selection in self.view.sel():
            self.view.insert(edit, selection.begin(), string)
