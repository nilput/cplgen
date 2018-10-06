'''
these are formatting functions of the various datastructures
'''
import sys
sys.path.append('.')
from ids import *

BLT = '•'

def pretty_symbol(symbol,ugly = 0):
    if symbol.val is not None:
        if ugly:
            return "%{} '{}'%".format(symbol.name, symbol.val)
        return "'{}'".format(symbol.val)
    return symbol.name

def pretty_seq(seq):
    s = ''
    for symbol in seq:
        s += ' {}'.format(pretty_symbol(symbol))
    return s

def pretty_rule(rule):
    return '{} -> {}'.format(rule.lhs, pretty_seq(rule.seq))

def pretty_rules(rls):
    s = ''
    for rule in rls:
        s += pretty_rule(rule) + '\n'
    return s
def pretty_productions(productions):
    s = ''
    for p in productions.values():
        s += pretty_rules(p.rules)
    return s

def pretty_rptr(rptr):
    s = ''
    s += '{} -> '.format(rptr.rule.lhs)
    for i, symbol in enumerate(rptr.rule.seq):
        if i == rptr.index:
            s += BLT 
        s += '{} '.format(pretty_symbol(symbol))
    if rptr.index == len(rptr.rule.seq):
        s += (BLT)
    return s

def pretty_item(item):
    s = ''
    s += '_{}_\n'.format(item.on)
    for rptr in item.rptrs:
        s += pretty_rptr(rptr) + '\n'
    return s

def pretty_item_goto(item):
    s = ''
    s += '_{}_GOTO_\n'.format(item.on)
    for k,v in item.goto.items():
        s += '[{}] -> _{}_\n'.format(k,v.on)
    return s

def pretty_slr_table(table, fwidth=9):
    s = ''
    prerow_fmt = 'state {:>3}'
    prerow_pad = ' ' * len(prerow_fmt.format(0))
    h = prerow_pad
    col_width = []
    for symbol in table.index_to_symbol:
        name = symbol.name 
        if symbol.name.startswith('T_LITERAL'):
            name += " ('{}')".format(symbol.val)
        width = max(fwidth, len(str(name))+2)
        h += '|{{:^{fwidth}}}'.format(fwidth=width).format(name)
        col_width.append(width)
    s += h + '\n' + ('-' * len(h)) + '\n'
    for i,row in enumerate(table.rows):
        s += prerow_fmt.format(i)
        for j,entry in enumerate(row):
            entry_str = nonpretty_slr_entry(entry) if entry else ''
            width = col_width[j]
            entry_str = entry_str[:width-1]
            s += '|{{:^{fwidth}}}'.format(fwidth=width).format(entry_str)
        s += '\n'
    return s

def indent(string, n):
    '''
    given a string of one or more lines indent it by n spaces,.
    '''
    return '\n'.join(map(lambda x: (' '*n) + x, string.split('\n')))


def pretty_slr_entry(entry):
    s = '{'
    s += 'action: {} {}'.format(global_rep(entry.action), entry.number)
    s += '}'
    return s
def nonpretty_slr_entry(entry):
    s = '{} {}'.format((global_rep(entry.action).replace('EA_', '').lower()+' ')[0],
                        entry.number)
    return s

def pretty_first_or_last(setfl):
    '''
    formats the sets: first() or last()
    '''
    s = ''
    for sym,first_of in setfl.items():
        s += '\n{} : '.format(sym)
        for f in first_of:
            s += '\n     {}'.format(f)
    s += '\n'
    return s
