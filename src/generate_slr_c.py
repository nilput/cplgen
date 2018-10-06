#!/usr/bin/env python3
'''
Author: nilputs@nilput.com
see COPYRIGHTS file which is included in this project
'''


import sys
import re
import argparse
import time
from pprint import pprint as pprint
from types import SimpleNamespace as nms
sys.path.append('.')
import lrgen
from ids import *
from format_types import indent

DEBUG = 0



#not used
def generate_C_rule_data(table):
    nprint('''\
struct rule_s rules_data[] = {''')
    for i,rule in enumerate(table.index_to_rule):
        # print(i, rule.lhs, file=sys.stderr) 
        # print(table.ctx.bnf.syms.get_symbol(rule.lhs).sym_num)
        if table.ctx.bnf.syms.get_symbol(rule.lhs) is None:
            print(rule,file=sys.stderr)
            print(table.ctx.bnf.syms.syms,file=sys.stderr)
            print(table.ctx.bnf.syms.syms['D'],file=sys.stderr)
            raise ValueError('none')
            
        nprint('{{ {rule_length:<{width}}, {rule_lhs:<{width}} }},'.format(rule_length = len(rule.seq),
                                                                           rule_lhs = table.ctx.bnf.syms.get_symbol(rule.lhs).sym_num,
                                                                           width=2))
    nprint('};\n')

def generate_C_states_data(table):
    nprint('''\
struct state_table_s states[{num_states}] = {{'''.format(num_states = len(table.rows)))

    nprint('\n')
    for i,row in enumerate(table.rows):
        nprint('''\
    {{''')
        for sym_idx,entry in enumerate(row):
            if entry is not None:
                entry_str = '{{ {},{} }},'.format(entry.action, entry.number) #when using .format(), {{ == {
            else:
                entry_str = '{ EA_REJ,EA_REJ }, '
            nprint('{:>{width}}'.format(entry_str, width=9))
        nprint('}},\n')


    nprint(sc('''
    };
    '''))


def generate_C_includes(table):
        nprint('#include "parse.h"\n')

def generate_represent_function(table,defs):
    nprint('const char *represent(int val){\n''')
    nprint('    switch (val){\n''')
    for k,v in defs.items():
        string = k if (not k.startswith('T_LITERAL')) else "'{}'".format(table.ctx.bnf.syms.syms[k].val)
        nprint('    case {}: return "{}";\n'.format(v,string))
    nprint('    default: return "INVALID_SYMBOL";\n')
    nprint('\n    }\n}\n')

def generate_C_parse_enum(table):
    enum = '\n#define DBG_PRINT' if DEBUG else ''
    enum+='''
enum PARSE_ENUM{{
    STACKLEN   = 100,
    SYMBOLSMAX = 50,
    {defs}
}};
'''
    ddict = {}
    for symbol in table.ctx.bnf.syms.syms.values():
            ddict[symbol.name] = symbol.sym_num

    enum_dict = {
            'EA_REDUCE':EA_REDUCE,
            'EA_ACC':   EA_ACC,
            'EA_SHIFT': EA_SHIFT,
            'EA_GOTO':  EA_GOTO,
            'EA_ACC'      :      EA_ACC ,
            'EA_REJ'      :      EA_REJ ,
            'EA_NONE'    :      EA_NONE ,
            }
    enum_dict.update(ddict)
    defs = '\n'
    for k,v in enum_dict.items():
        defs += '    {k} = {v},\n'.format(k=k, v=v)
    nprint(enum.format(defs = defs))
    if DEBUG:
        generate_represent_function(table,enum_dict)

def generate_C_data(table):
    generate_C_parse_enum(table)
    generate_C_includes(table)
    generate_C_states_data(table)
    generate_C_rule_data(table)

def genereate_basic_lexer(table):
    nprint('''
int next_input(){
    static char buff[128];
    static int idx = 0;
    int r;

    r = fgetc(stdin);
    while (1){
        switch(r){
            case ' ':
            case '\\n':
            case '\\t':
                r = fgetc(stdin);
                continue;
        }
        break;
    }

    if (r != EOF){
        buff[idx++] = r;
        buff[idx] = 0;
        printf("read '%s'\\n", buff);
    }
    ''')

    written = 0
    for i,symbol in enumerate(table.index_to_symbol):
        if not symbol.name.startswith('T_LITERAL'):
            continue
        c = '' if written == 0 else 'else '
        c += '''if (strncmp({arg0},{arg1},{slen}) == 0){{
            return {rv};
        }}
        '''
        
        c = c.format( arg0 = 'buff+idx-1',
                      arg1 = '"{}"'.format(symbol.val),
                      slen = '{}'.format(len(symbol.val)),
                      rv   =  '{}'.format(symbol.sym_num) )
        written += 1
        nprint(c)

    nprint('''
    if (r == EOF || r == ';'){
        return _END;
    }
}
    ''')


def sc(code):
        #strips code
    s = ''
    split = code.split('\n')
    for line in split:
        if not re.match(r'\s*$', line):
            s += line
            s += '\n'
    return s

def nprint(*args, **kwargs):
    print(*args, **kwargs, end='')

def parse_int(string):
    try:
        return int(string)
    except:
        return None

def fix_arb_code(rule_length, arb_code):
    '''
    turns stuff like $1 into a stack offset

    if we have a rule P -> T1 T2 T3 
                      p -> T1 T2 T3 NEWP
                                    ^idx
                      P's LEN is 3
    then their offsets are:
                      $$ is just whats at idx
                      $n
                      P -> T(idx-LEN+n-1)
                      so $1 points to T1, $2 to T2 and so on
    '''
    c = arb_code
    template = '(p->symbol_stack.data[( p->symbol_stack.idx - ({rule_len}) + {offset} - 1)])'
    for m in re.finditer(r'\$(\d+)', c):
        off = m.group(1)
        n = parse_int(off)
        if (not n) or (n < 1) or (n > rule_length):
            lrgen.err('$n offset is out of rule length boundary: "{}"'.format(m.group(0)))
        c = c.replace(m.group(0), template.format(offset=off, rule_len=rule_length))
    c = c.replace('$$', '(p->symbol_stack.data[p->symbol_stack.idx])')
    return c

def generate_C_code(table):
    genereate_basic_lexer(table)
    nprint('\n')
    rule_numbers = []

    for i,rule in enumerate(table.index_to_rule):
        #reduce functions return the next state function pointer that  we should goto
        #accept and reject states return null so that the driving loop exits
        nprint(sc('''
static void reduce_{rule_num}_action(struct parse_info_s *p)
{{
        //rule: {rule}
               '''.format(rule_num=i, rule=lrgen.pretty_rule(rule))))


        if len(rule.seq) == 1 and rule.seq[0].val: #copy literal
            nprint('''p->symbol_stack.data[p->symbol_stack.idx].input = '{}';'''.format(rule.seq[0].val[0]))
        code = rule.arbcode.val if rule.arbcode else ''
        nprint('\n',fix_arb_code(len(rule.seq),code))

        if DEBUG:
            nprint('printf("{rule}\\nlhs input: %d\\n",p->symbol_stack.data[p->symbol_stack.idx].input);\n'.format(rule=lrgen.pretty_rule(rule).replace('"','\\"')));
            # nprint('''printf("np:%d\\n user:%d\\n", p->symbol_stack.data[p->symbol_stack.idx].input,p->symbol_stack.data[p->symbol_stack.idx].data.n );''')

        nprint('\n}\n')
        rule_numbers += [rule.rule_num]

    nprint(sc('''
void reduce_action(struct parse_info_s *p, int rule_num){
    switch(rule_num){
    '''))

    for rule_num in rule_numbers:
        nprint(sc('''
        case {rule_num}:
            reduce_{rule_num}_action(p);
            break;
        '''.format(rule_num=rule_num)))
        
    nprint(sc('''
    default:
        runtime_error();
        break;
    }
}
    '''))
    
    generate_C_main(table)


def generate_C_main(table):
    nprint('\n#include "simple_lr_main.h"')

def parse_cmd_line_args():
    '''
    parses command line args, returns a dictionary of them
    '''
    stdin_linux = '/dev/fd/0'
    parser = argparse.ArgumentParser(description='vcpu assembler')
    parser.add_argument('--in', default=stdin_linux,
            help='input file')
    parser.add_argument('--out', default='p.out',
            help='out file')
    parser.add_argument('-v', action='store_true')

    args = vars(parser.parse_args())
    for i in range(sys.argv.count('-v')):
        global DEBUG
        DEBUG += 1
    return args

def main():
    global TSRC

    args = parse_cmd_line_args()
    input_str = open(args['in']).read()
    lrgen.TSRC = lrgen.token_source(input_str)

    ast   = lrgen.grammar() #returns a tree like dictionary (SimpleNamespace tree)
    bnf   = lrgen.extract_bnf(ast) #bnf, contains .productions and .syms (grammar and symbol table)
    ctx   = lrgen.create_states(bnf) #(contains .items (states))
    table = lrgen.generate_slr_table(ctx) #turns the .items into a table
    #uses table to generate a parser
    generate_C_data(table) 
    generate_C_code(table)


if __name__ == '__main__':
    main()
