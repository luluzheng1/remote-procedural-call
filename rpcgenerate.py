#!/bin/env python
import subprocess
import os
import json
import sys

IDL_TO_JSON_EXECUTABLE = './idl_to_json'
# Array variable names for generic templated array parsers
ARRAY_SIZE_VARS = ['X', 'Y', 'Z', 'A', 'B', 'C', 'D', 'E',
                   'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q']
# Parsers for Builtin Types
int_parser = \
    """
int parse_int(stringstream &strm)
{
    int x;
    strm >> x;
    return x;
}
"""

float_parser = \
    """
float parse_float(stringstream &strm)
{
    float x;
    strm >> x;
    return x;
}
"""

string_parser = \
    """
string parse_string(stringstream &strm)
{
    int length;
    strm >> length;
    string s;
    strm.ignore(1);
    s.resize(length);
    strm.read(&s[0], length);
    return s;
}
"""

# Serializers from Builtin Types
int_serializer = \
    """
string serialize_int(int x)
{
    return to_string(x);
}
"""

float_serializer = \
    """
string serialize_float(float x)
{
    return to_string(x);
}
"""

string_serializer = \
    """
string serialize_string(string s)
{
    string msg;
    msg += to_string(s.length());
    msg += \" \";
    msg += s;
    return msg;
}
"""

bad_function = \
    """
void __badFunction(char *functionName)
{
    exit(EXIT_FAILURE);

}
"""

get_data_from_stream = \
    """
void getDataFromStream(char *buffer, unsigned int bufSize)
{
    unsigned int i;
    char *bufp; // next char to read
    bool readnull;
    ssize_t readlen; // amount of data read from socket

    readnull = false;
    bufp = buffer;
    for (i = 0; i < bufSize; i++)
    {
        readlen = RPCSTUBSOCKET->read(bufp, 1); // read a byte
        // check for eof or error
        if (readlen == 0)
        {
            break;
        }
        // check for null and bump buffer pointer
        if (*bufp++ == '\\0')
        {
            readnull = true;
            break;
        }
    }

    if (readlen == 0)
    {
        if (RPCSTUBSOCKET->eof())
        {
            c150debug->printf(C150RPCDEBUG, "stub: EOF signaled on input");
        }
        else
        {
            throw C150Exception("stub: unexpected zero length read without eof");
        }
    }

    else if (!readnull)
        throw C150Exception("stub: data received not null terminated or too long");

}
"""

# Checks if filename specified on command line is valid


def is_file_valid(filename):
    if (not os.path.isfile(filename)):
        print("Path %s does not designate a file" % filename, file=sys.stderr)
        raise Exception("No file named " + filename)
    if (not os.access(filename, os.R_OK)):
        print("File %s is not readable" % filename, file=sys.stderr)
        raise Exception("File " + filename + " not readable")
    if (not os.path.isfile(IDL_TO_JSON_EXECUTABLE)):
        print("Path %s does not designate a file...run \"make\" to create it" %
              IDL_TO_JSON_EXECUTABLE, file=sys.stderr)
        raise Exception("No file named " + IDL_TO_JSON_EXECUTABLE)

    if (not os.access(IDL_TO_JSON_EXECUTABLE, os.X_OK)):
        print("File %s exists but is not executable" %
              IDL_TO_JSON_EXECUTABLE, file=sys.stderr)
        raise Exception("File " + IDL_TO_JSON_EXECUTABLE + " not executable")


def array_type(ty):
    end_pos = ty.find("[")
    return ty[2:end_pos]

# Return array size in a list up to N dimensions


def array_size(ty):
    ty = ty[2:]
    ty = ty.replace("][", "_")
    ty = ty.replace("[", "_")
    ty = ty.replace("]", "")
    l = ty.split("_")[1:]
    return l

# Format array parser and serializer function names


def format_array_funname(ty):
    dimension = len(ty.split("[")) - 1
    # string replace "][" with "_"
    if ty[:2] == "__":
        ty = ty[2:]
    ty = ty.replace("][", "_")
    # string replace "[" with "_"
    ty = ty.replace("[", str(dimension) + "DArray_")
    # string replace "]" with "_array_"
    ty = ty.replace("]", "")
    return ty


def format_array_arg(n, ty):
    start = ty.find("[")
    end = len(ty)
    return array_type(ty) + " " + n + ty[start:end]


def forward_declarations(x, f, decls):
    for ty, sig in decls["types"].items():
        if sig["type_of_type"] == "struct":
            f.write(struct_serializer_fdecl(ty, sig) + ";\n")
            f.write(struct_parser_fdecl(ty, sig) + ";\n")
        elif sig["type_of_type"] == "array":
            f.write(array_serializer_fdecl(ty, sig) + ";\n")

            dimension = len(ty.split("[")) - 1
            array_ty = array_type(ty)
            if (dimension, array_ty) not in x.array_dimensions:
                f.write(array_parser_fdecl(
                    ty, sig, dimension, array_ty) + ";\n")
                x.array_dimensions.add((dimension, array_ty))
        elif sig["type_of_type"] == "builtin":
            continue
    f.write("\n")


def array_parser_fdecl(ty, sig, dimension, array_ty):
    template_decl = "template <"
    array_size = ""
    for i in range(dimension):
        template_decl += "int " + ARRAY_SIZE_VARS[i]
        array_size += "[" + ARRAY_SIZE_VARS[i] + "]"

        if i != dimension - 1:
            template_decl += ", "
    template_decl += ">\n"

    fundecl = "void parse_" + array_ty + \
        str(dimension) + "DArray(stringstream &strm, " + \
        array_ty + " " + "(&array)" + array_size + ")"
    return template_decl + fundecl


def array_serializer_fdecl(ty, sig):
    size_list = array_size(ty)

    arg_type = array_type(ty) + " array"
    fundecl = "string serialize_" + format_array_funname(ty) + "("

    for size in size_list:
        arg_type += "[" + size + "]"

    fundecl += arg_type + ")"
    return fundecl

# Generate a specific serializer for an nDarray with type ty and dimension n


def create_array_serializer(ty, sig):
    fundecl = array_serializer_fdecl(ty, sig) + "\n"
    body = "\tstring msg;\n"
    body += "\tint size = " + str(sig["element_count"]) + ";\n"
    body += "\tfor (int i = 0; i < size; i++)\n"
    body += "\t{\n"
    body += "\t\tmsg += serialize_" + \
        format_array_funname(sig["member_type"]) + "(array[i]);\n"
    body += "\t\tif(i != size - 1)\n"
    body += "\t\t\tmsg += \" \";\n"
    body += "\t}\n"
    body += "\treturn msg;\n"

    return fundecl + "{\n" + body + "}\n"


def struct_serializer_fdecl(ty, sig):
    arg = "struct__" + ty[0].lower()
    return "string serialize_" + ty + "(" + ty + " " + arg + ")"


def struct_parser_fdecl(ty, sig):
    return ty + " " + "parse_" + ty + "(stringstream &strm)"


def create_struct_serializer(ty, sig):
    fundecl = struct_serializer_fdecl(ty, sig) + "\n"
    arg = "struct__" + ty[0].lower()
    body = "\tstring msg = \"\";\n"

    for i, member in enumerate(sig["members"]):
        if member["type"][:2] == "__":
            funname = format_array_funname(member["type"])
        else:
            funname = member["type"]
        body += "\tmsg += serialize_" + funname + \
            "(" + arg + "." + member["name"] + ");\n"
        if i != len(sig["members"]) - 1:
            body += "\tmsg += \" \";\n"

    body += "\treturn msg;\n"

    serializer = fundecl + "{\n" + body + "}\n"
    return serializer


def create_struct_parser(ty, sig):
    fundecl = struct_parser_fdecl(ty, sig) + "\n"
    arg = "struct__" + ty[0].lower()
    body = "\t" + ty + " " + arg + ";\n"

    for member in sig["members"]:
        mty = member["type"]
        if mty[:2] == "__":
            dimension = len(mty.split("[")) - 1
            funname = array_type(mty) + str(dimension) + "DArray"
            body += "\tparse_" + \
                funname + \
                    "(strm, {memb});\n".format(
                        memb=arg + "." + member["name"])
        else:
            funname = mty
            body += "\t" + arg + "." + member["name"] + " = " + "parse_" + \
                funname + "(strm);\n"

    body += "\treturn " + arg + ";\n"

    parser = fundecl + "{\n" + body + "}\n"
    return parser


class ProxyGenerator:
    def __init__(self, idl_filename):
        self.idl = idl_filename
        self.h_files = self.get_h_files()
        self.libraries = self.get_libraries()
        self.proxy = self.proxy_name()
        self.builtin_parsers = [int_parser, float_parser, string_parser]
        self.builtin_serializers = [int_serializer,
                                    float_serializer, string_serializer]
        self.array_dimensions = set()

    def get_h_files(self):
        headers = ["rpcproxyhelper.h", "c150debug.h"]
        return headers

    def get_libraries(self):
        return ["stdio.h", "stdlib.h", "cstdio", "cstring", "string", "sstream", "memory", "iostream"]

    def proxy_name(self):
        idl_file = self.idl[: self.idl.index(".")]
        return idl_file + ".proxy.cpp"

    # Generate boilerplate proelf.array_dimensions = set()xy.cpp file with dependencies,
    # builtin parsers and serializers
    def create_template(self, f):
        h_files = list(
            map((lambda x: "#include \"" + x + "\"\n"), self.h_files))
        libraries = list(
            map((lambda x: "#include <" + x + ">\n"), self.libraries))
        f.writelines(libraries)
        f.writelines(h_files)
        f.write("using namespace std;\n")
        f.write("using namespace C150NETWORK;\n")
        f.write("#include \"" + self.idl + "\"\n")

    def write_builtin_parsers(self, f):
        f.writelines(self.builtin_parsers)

    def write_builtin_serializers(self, f):
        f.writelines(self.builtin_serializers)

    # Generate a generic array parser for nDarray of type ty and dimenson n
    def create_array_parser(self, ty, sig, dimension, array_ty):
        fundecl = array_parser_fdecl(ty, sig, dimension, array_ty) + "\n"
        body = "\tfor (int i = 0; i < " + ARRAY_SIZE_VARS[0] + "; i++)\n"
        body += "\t{\n"
        if dimension == 1:
            body += "\t\tarray[i] = parse_" + array_ty + "(strm);\n"
        else:
            body += "\t\tparse_" + array_ty + \
                str(dimension-1) + "DArray(strm, array[i]);\n"
        body += "\t}\n"

        self.array_dimensions.add((dimension, array_ty))
        return fundecl + "{\n" + body + "}\n"

    def create_function_serializer(self, funname, sig):
        return_ty = sig["return_type"]
        a = []
        for arg in sig["arguments"]:
            if arg["type"][:2] == "__":
                a.append(format_array_arg(arg["name"], arg["type"]))
            else:
                a.append(arg["type"] + " " + arg["name"])

        args = ", ".join(a)
        fundecl = "string serialize_{fn}({params})\n".format(
            fn=funname, params=args)

        body = "\tstring msg;\n"

        a.clear()
        for arg in sig["arguments"]:
            if arg["type"][:2] == "__":
                ty = format_array_funname(arg["type"])
            else:
                ty = arg["type"]
            a.append(
                "\tmsg += serialize_{t}({n});\n".format(t=ty, n=arg["name"]))

        body += "\tmsg += \" \";\n".join(a)
        body += "\treturn msg;\n"

        return fundecl + "{\n" + body + "}\n"

    def create_top_level_function(self, name, sig):
        return_ty = sig["return_type"]
        fundecl = return_ty + " " + name + "("

        a = []
        arg_list = []
        for arg in sig["arguments"]:
            arg_ty = arg["type"]
            arg_name = arg["name"]
            arg_list.append(arg_name)
            if arg_ty[:2] == "__":
                start = arg_ty.find("[")
                end = len(arg_ty)
                param = array_type(arg_ty) + " " + \
                    arg_name + arg_ty[start:end]
            else:
                param = arg_ty + " " + arg_name
            a.append(param)
        fundecl += ", ".join(a) + ")\n"
        body = ""

        if return_ty == "int" or return_ty == "float":
            body = "\tchar readBuffer[50];\n"
        elif return_ty != "void":
            body = "\tchar readBuffer[1000000];\n"

        body += "\tstring funName = \"" + name + "\";\n"
        body += "\tRPCPROXYSOCKET->write(funName.c_str(), funName.length() + 1);\n"
        body += "\t*GRADING << \"Client sending function name " + name + "\" << endl;\n"
        body += "\tstring data = serialize_" + name + \
            "(" + ", ".join(arg_list) + ");\n"
        body += "\tRPCPROXYSOCKET->write(data.c_str(), data.length() + 1);\n"
        body += "\t*GRADING << \"Client sending serialized data for " + \
            name + "(" + ", ".join(arg_list) + ")\" << endl;\n"
        if return_ty != "void":
            body += "\tRPCPROXYSOCKET->read(readBuffer, sizeof(readBuffer));\n"
            body += "\tstring str(readBuffer);\n"
            body += "\tstringstream data_strm(str);\n"
        if return_ty[:2] == "__":
            return_ty = self.format_array_funname(return_ty)
        else:
            return_ty
        if return_ty != "void":
            body += "\t*GRADING << \"Client received return value of type {ty} for {n}\" << endl;\n".format(
                ty=return_ty, n=name)
            body += "\treturn parse_" + return_ty + "(data_strm);\n"
        else:
            body += "\t*GRADING << \"Client received return value of type void for {n}\" << endl;\n".format(
                n=name)
            body += "\treturn;\n"

        return fundecl + "{\n" + body + "}\n"


class StubGenerator:
    def __init__(self, idl_filename):
        self.idl = idl_filename
        self.h_files = self.get_h_files()
        self.libraries = self.get_libraries()
        self.stub = self.stub_name()
        self.builtin_parsers = [int_parser, float_parser, string_parser]
        self.builtin_serializers = [int_serializer,
                                    float_serializer, string_serializer]
        self.array_dimensions = set()

    def get_h_files(self):
        headers = ["rpcstubhelper.h", "c150debug.h"]
        return headers

    def get_libraries(self):
        return ["stdio.h", "stdlib.h", "cstdio", "cstring", "string", "sstream", "memory", "iostream"]

    def stub_name(self):
        idl_file = self.idl[: self.idl.index(".")]
        return idl_file + ".stub.cpp"

    # Generate boilerplate proelf.array_dimensions = set()xy.cpp file with dependencies,
    # builtin parsers and serializers
    def create_template(self, f):
        h_files = list(
            map((lambda x: "#include \"" + x + "\"\n"), self.h_files))
        libraries = list(
            map((lambda x: "#include <" + x + ">\n"), self.libraries))
        f.writelines(libraries)
        f.writelines(h_files)
        f.write("using namespace std;\n")
        f.write("using namespace C150NETWORK;\n")
        f.write("#include \"" + self.idl + "\"\n")

    def write_builtin_parsers(self, f):
        f.writelines(self.builtin_parsers)

    def write_builtin_serializers(self, f):
        f.writelines(self.builtin_serializers)

    # Generate a generic array parser for nDarray of type ty and dimenson n
    def create_array_parser(self, ty, sig, dimension, array_ty):
        fundecl = array_parser_fdecl(ty, sig, dimension, array_ty) + "\n"
        body = "\tfor (int i = 0; i < " + ARRAY_SIZE_VARS[0] + "; i++)\n"
        body += "\t{\n"
        if dimension == 1:
            body += "\t\tarray[i] = parse_" + array_ty + "(strm);\n"
        else:
            body += "\t\tparse_" + array_ty + \
                str(dimension-1) + "DArray(strm, array[i]);\n"
        body += "\t}\n"

        self.array_dimensions.add((dimension, array_ty))
        return fundecl + "{\n" + body + "}\n\n"

    def create_function_parser(self, name, sig):
        fundecl = "void parse_" + name + "(stringstream &strm)\n"
        body = ""
        arg_list = []
        for arg in sig["arguments"]:
            arg_name = arg["name"]
            arg_ty = arg["type"]
            arg_list.append(arg_name)
            if arg_ty[:2] == "__":
                array_ty = array_type(arg_ty)
                array_dim = len(arg_ty.split("[")) - 1
                body += "\t" + format_array_arg(arg_name, arg_ty) + ";\n"
                body += "\tparse_{t}{d}DArray(strm, {n});\n".format(
                    t=array_ty, d=array_dim, n=arg_name)
            else:
                # handle other case
                body += "\t{t} {n};\n".format(t=arg_ty, n=arg_name)
                body += "\t{n} = parse_{t}(strm);\n".format(t=arg_ty,
                                                            n=arg_name)

        body += "\t__{fun}(".format(fun=name) + ", ".join(arg_list) + ");\n"
        return fundecl + "{\n" + body + "}\n\n"

    def create_top_level_function(self, name, sig):
        return_ty = sig["return_type"]
        funname = "__" + name
        p = []
        a = []
        for arg in sig["arguments"]:
            arg_name = arg["name"]
            arg_ty = arg["type"]
            a.append(arg_name)
            if arg_ty[:2] == "__":
                p.append(format_array_arg(arg_name, arg_ty))
            else:
                p.append(arg_ty + " " + arg_name)
        params = ", ".join(p)
        fundecl = return_ty + " " + funname + "(" + params + ")\n"
        body = ""
        if return_ty == "void":
            body = "\t" + name + "(" + ", ".join(a) + ");\n"
            body += "\treturn;\n"
        else:
            body = "\t" + return_ty + " res = " + \
                name + "(" + ", ".join(a) + ");\n"
            body += "\t*GRADING << \"Server received request to invoke " + \
                name + "(" + ", ".join(a) + ")\" << endl;\n"
            body += "\tstring str_res = serialize_" + return_ty + "(res);\n"
            body += "\tRPCSTUBSOCKET->write(str_res.c_str(), str_res.length() + 1);\n"
            body += "\t*GRADING << \"Server sent return value of type " + return_ty + " for " + \
                funname[2:] + "(" + params + ")\" << endl;\n"
            body += "\treturn res;\n"

        return fundecl + "{\n" + body + "}\n\n"

    def dispatch_function(self, funnames):
        fundecl = "void dispatchFunction()\n"
        body = \
            """
    char functionNameBuffer[50];
    char dataBuffer[1000000];
    getDataFromStream(functionNameBuffer, sizeof(functionNameBuffer));
    getDataFromStream(dataBuffer, sizeof(dataBuffer));
    string str(dataBuffer);
    stringstream data_strm(str);
    if (!RPCSTUBSOCKET->eof())
    {
        """
        body += "if (strcmp(functionNameBuffer, \"" + \
            funnames[0] + "\") == 0)\n"
        body += "\t\t\tparse_" + funnames[0] + "(data_strm);\n"

        for n in funnames[1:]:
            body += "\t\telse if (strcmp(functionNameBuffer, \"" + \
                n + "\") == 0)\n"
            body += "\t\t\tparse_" + n + "(data_strm);\n"

        body += "\t\telse\n\t\t\t__badFunction(functionNameBuffer);\n"
        body += "\t}\n"
        return fundecl + "{\n" + body + "}\n"


def stub_main(idl):
    x = StubGenerator(idl)
    f = open(x.stub, 'w')
    x.create_template(f)

    # traverse through JSON
    if len(sys.argv) != 2:
        raise Exception("Wrong number of arguments")

    filename = sys.argv[1]
    is_file_valid(filename)

    decls = json.loads((subprocess.check_output(
        [IDL_TO_JSON_EXECUTABLE, filename]).decode('utf-8')))

    forward_declarations(x, f, decls)
    f.write(bad_function + "\n")
    f.write(get_data_from_stream + "\n")
    x.write_builtin_parsers(f)
    x.write_builtin_serializers(f)
    x.array_dimensions.clear()

    for ty, sig in decls["types"].items():
        # Create serializer and parser for each type in proxy.cpp
        if sig["type_of_type"] == "struct":
            f.write(create_struct_serializer(ty, sig) + "\n")
            f.write(create_struct_parser(ty, sig) + "\n")
        elif sig["type_of_type"] == "array":
            f.write(create_array_serializer(ty, sig) + "\n")

            dimension = len(ty.split("[")) - 1
            array_ty = array_type(ty)
            if (dimension, array_ty) not in x.array_dimensions:
                f.write(x.create_array_parser(
                    ty, sig, dimension, array_ty) + "\n")
        elif sig["type_of_type"] == "builtin":
            continue

    for name, sig in decls["functions"].items():
        f.write(x.create_top_level_function(name, sig))
        f.write(x.create_function_parser(name, sig))

    # TODO: dispatch function
    f.write(x.dispatch_function(list(decls["functions"].keys())))


def proxy_main(idl):
    x = ProxyGenerator(idl)
    f = open(x.proxy, 'w')
    x.create_template(f)

    # traverse through JSON
    if len(sys.argv) != 2:
        raise "Wrong number of arguments"

    filename = sys.argv[1]
    is_file_valid(filename)

    decls = json.loads((subprocess.check_output(
        [IDL_TO_JSON_EXECUTABLE, filename]).decode('utf-8')))

    forward_declarations(x, f, decls)
    x.write_builtin_parsers(f)
    x.write_builtin_serializers(f)
    x.array_dimensions.clear()
    # TODO: empty parsers for empty structs?
    for ty, sig in decls["types"].items():
        # Create serializer and parser for each type in proxy.cpp
        if sig["type_of_type"] == "struct":
            f.write(create_struct_serializer(ty, sig) + "\n")
            f.write(create_struct_parser(ty, sig) + "\n")
        elif sig["type_of_type"] == "array":
            f.write(create_array_serializer(ty, sig) + "\n")

            dimension = len(ty.split("[")) - 1
            array_ty = array_type(ty)
            if (dimension, array_ty) not in x.array_dimensions:
                f.write(x.create_array_parser(
                    ty, sig, dimension, array_ty) + "\n")
        elif sig["type_of_type"] == "builtin":
            continue

    for name, sig in decls["functions"].items():
        f.write(x.create_function_serializer(name, sig))
        f.write(x.create_top_level_function(name, sig))

    f.close()


def main():
    idl = sys.argv[1]
    proxy_main(idl)
    stub_main(idl)


if __name__ == "__main__":
    main()
