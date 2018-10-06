#!/usr/bin/env python3
'''
Author: nilputs@nilput.com
see COPYRIGHTS file which is included in this project
'''
'''
 generates a states table, currently only supports slr(1) grammars
'''

import sys
import re
import time

import argparse
from nms import nms
sys.path.append('.')
from ids import *
from format_types import *

'''
example input grammar:
    note: every grammar has to start like this: 
    _START -> whatever_production _END

    the values _START and _END are treated differntly


    TARGET -> sym0 sym1 'imm' sym2 {arbitrary;}
           | sym4 D {arbitrary;}
    D      -> sym5  '+' W
    W      -> '-' W {
                        if (true){
                            arbitrary code;
                        }
                    }
    expr -> term '+' factor {
            //inspired by yacc's syntax
            //$$ refers to the lhs production
            //$1 in this case refers to term, and $3 to the factor
            //note that (n) has to exist as a member of your struct
            $$.n = $1.n + $3.n;
    }

the parser generator parser itself is recursive descent
the definition for its grammar
    grammar     -> def_list
    def_list    -> ddef def_list
                | ddef
    ddef         -> goal_name T_DRV_SYMBOL rule_list
    rule_list    -> rule T_OR_SYMBOL rule_list
                | rule 
    rule         -> symlist arb_code

    arb_code    -> T_ARB_CODE
                | NIL
    symlist     -> symbol symlist
                | symbol
    symbol      -> goal_name
                | terminal
    goal_name   -> T_IDENTIFER #doesnt start with T_
    terminal    -> T_LITERAL     #quoted string like: '+'
                | T_T_IDENTIFER #prefixed by T_, recognized by the external lexer (not implementd currently)
'''

TSRC = None
DEBUG = 0


def get_block(string, idx):
    '''
    given a string and an index for '{' in the string
    it returns when does the block end (ignoring nested ones)
    '''
    brack_beg, brack_end = ('{','}')
    if string[idx] != brack_beg:
        return None
    nested = 1
    start = idx
    idx += 1
    while idx < len(string):
        if string[idx] == brack_beg:
            nested += 1
        elif string[idx] == brack_end:
            nested -= 1
            if nested == 0:
                break
        idx += 1
    if string[idx] == brack_end:
        return (start, idx + 1)
    return None


token_defs = (\
                (T_WHITESPACE   ,   r'[ \t]+'                                                       , (0,0)     ), \
                (T_NEWL         ,   r'\n'                                                           , (0,0)     ), \
                (T_COMMENT      ,   r'#[^\n]*\n'                                                    , (0,0)     ), \
                (T_T_IDENTIFER  ,   r'T_[a-zA-Z0-9_]+'                                              , (0,0)     ), \
                (T_IDENTIFER    ,   r'[a-zA-Z_]+'                                                   , (0,0)     ), \
                (T_LITERAL      ,   r"'([^']+)'"                                                    , (1,0)     ), \
                (T_OR_SYMBOL    ,   r'\|'                                                           , (0,0)     ), \
                (T_DRV_SYMBOL   ,   r'->'                                                           , (0,0)     ), \
                (T_ARB_CODE     ,   r'{'                                                            , get_block ), \
             )

'''
special tokens that should probably be parsed as tokens with different tids: (now they're not, they're just treated differently)
_START
_END
_EPSILON
'''

class coord:
    '''
    a class storing information about where was a token encountered (filename, lineno, colno)
    '''
    def __init__(self, filename, lineno, colno):
        self.filename = filename
        self.lineno = lineno
        self.colno = colno
    def __repr__(self):
        return '%s:%d' % (self.filename, self.lineno)
    def verbose_repr(self):
        return self.__repr__() + (':%d' % (self.colno))

class token:
    '''
    a class representing a token
    .tid: token id
    .val: its value (string)
    .xyz: its position (a coord object)
    '''
    def __init__(self, tid, val, xyz):
        self.tid = tid
        self.val = val
        self.xyz = xyz
    def tidval(self):
        return self.tid, self.val
    def is_eof(self):
        return self.tid == T_END
    def is_invalid(self):
        return self.tid is None
    @property
    def tid_str(self):
        return global_rep(self.tid)
    def __bool__(self):
        return (not self.is_invalid()) and (not self.is_eof())
    def __repr__(self):
        if not self:
            return '(token %s, %s, %s)' % (self.tid_str if self.tid is not None else 'INVALID',
                                       self.val,
                                       self.xyz)
        return '(token %s, "%s")' % (self.tid_str, self.val)


class token_source:
    '''
    a class that is initialized with a (fp (.open())able) or a string
    it tokenizes it according to token_defs, it has methods for skipping, getting, and ungetting tokens
    ungetting tokens is only relevant if we are dealing with grammars that involve backtracking, or in this case inefficient and lazily designed ones :)
    '''
    DEFAULT_STACK_MAX = 5
    DEFAULT_SKIP = (T_WHITESPACE, T_NEWL, T_COMMENT)
    def __init__(self, input_src):
        if hasattr(input_src, 'read'):
            self.content = input_src.read()
            self.filename = input_src.name
        else:
            assert isinstance(input_src, str)
            self.content = input_src
            self.filename = ''
        self.idx = 0
        self.lineno = 1
        self.undo_stack = [(self.idx, self.lineno)]


    def next_token(self, skip=DEFAULT_SKIP):
        '''
        returns a token() object whenever it finds a match
        when it consumes the entire input it returns an eof token (token.is_eof() true)
        when it doesn't recognize the input it returns a token where token.is_invalid() returns true
        in the last two cases if (token) will be false
        
        skip can be a list of token types to be skipped, use None to not skip anything, 
        by default whitespaces are skipped
        '''
        if skip is None:
            skip = ()
        self.skip(skip)
        return self._next_token()
    def _next_token(self):
        '''
        internal
        '''
        for tid, regex, skip_tpl in token_defs:
            reobj = re.compile(regex)
            m = reobj.match(self.content, self.idx)
            if m:
                if isinstance(skip_tpl, tuple):
                    grp, skip_to = skip_tpl
                    if (m.span(skip_to)[1] - self.idx) <= 0:
                        raise RuntimeError(("infinite loop detected in next_token()," +\
                                            "regex: '{}' idx: '{}'").format(regex, self.idx))
                    self.undo_stack.append((self.idx, self.lineno,))
                    if len(self.undo_stack) > token_source.DEFAULT_STACK_MAX:
                        self.undo_stack = self.undo_stack[-token_source.DEFAULT_STACK_MAX:]
                    advance_to = m.span(skip_to)[1]
                    val = m.group(grp)
                else:
                    #it's a function
                    self.undo_stack.append((self.idx, self.lineno,))
                    rv = skip_tpl(self.content, self.idx)
                    if rv is None:
                        continue
                    beg, end = rv
                    val = self.content[beg:end]
                    advance_to = end

                t = token(tid, val, coord(self.filename, self.lineno, self.colno))
                self.lineno += self.count_lines(val)
                self.idx = advance_to
                if DEBUG:
                    print('next token:',t)
                    self.dbg_last_tok = t
                return t
        self.undo_stack.append((self.idx, self.lineno,))
        if self.idx >= len(self.content):
            return token(T_END, None, coord(self.filename, self.lineno, self.colno))
        return token(None, None, coord(self.filename, self.lineno, self.colno))

    def count_lines(self, val):
        return val.count('\n')

    def skip(self, what = DEFAULT_SKIP):
        tok = self._next_token()
        while tok.tid in what:
            dprint(1, 'skipped:' ,tok)
            tok = self._next_token()
        dprint(1, '(unskipped): ',end='')
        self.unget()

    def unget(self):
        if DEBUG:
            try:
                dprint('ungetting', self.dbg_last_tok)
            except: 
                pass

        if not self.undo_stack:
            raise RuntimeError("unget(): attempted to undo more than the default allowed size, idx: {}".format(self.idx))
        self.idx, self.lineno = self.undo_stack.pop()

    @property
    def colno(self):
        prv = self.content.rfind('\n',0, self.idx)
        if prv == -1:
            return 0
        return self.idx - prv

def ensure(what, skip_what = None):
    '''
    it tries to get a token with a tid matching the 'what' argument, while skipping what's specified in the skip_what tuple
    it makes sure the token stream is at the first non-skipped position if it can't get it
    '''
    args = ()
    if skip_what:
        args = (skip_what,)
    nxt = TSRC.next_token(*args)
    if nxt.tid != what:
        TSRC.unget()
        return None
    return nxt




def err(m):
    '''
    print an error and exit the python interpreter
    '''
    print(m, file=sys.stderr)
    sys.exit(1)



'''
Top down parser for bnf grammar
todo: left factor
'''
def goal_name():
    dprint(1, 'goal_name: ',end='')
    #ends on newline
    return ensure(T_IDENTIFER, (T_WHITESPACE,T_COMMENT))

def terminal():
    dprint(1, 'terminal: ',end='')
    #ends on newline
    t = ensure(T_T_IDENTIFER, (T_WHITESPACE,))
    if not t:
        t = ensure(T_LITERAL, (T_WHITESPACE,))
    return t

def symbol():
    dprint(1, 'symbol: ',end='')
    s = goal_name()
    if not s:
        s = terminal()
    #could be none
    return s

def symlist():
    dprint(1, 'symlist: ',end='')
    s = symbol()
    if not s:
        return s
    slist = symlist()
    if not slist:
        slist = [s]
    else:
        slist = [s] + slist
    dprint(1, 'symlist ', slist)
    return slist

def arb_code():
    dprint(1, 'arb_code: ',end='')
    return ensure(T_ARB_CODE, ensure(T_WHITESPACE,))

def rule():
    dprint(1, 'rule: ',end='')
    slist = symlist()
    if not slist:
        return slist
    arbcode = arb_code()
    return [slist, arbcode]

def rule_list():
    dprint(1, 'rule_list: ',end='')
    rulelist = []
    a = rule()
    while a:
        rulelist.append(a)
        dprint(1, 'expecting | or a New rule')
        or_symbol = ensure(T_OR_SYMBOL)
        if not or_symbol:
            break
        a = rule()
    return rulelist

def ddef():
    '''
    ddef -> goal_name T_DRV_SYMBOL rule_list
    '''
    definition = nms()
    dprint(1, 'ddef: ',end='')
    gn = goal_name()
    if not gn:
        dprint(1, 'no goalname')
        return gn
    definition.goalname = gn

    #discarded but needed
    if not ensure(T_DRV_SYMBOL, (T_WHITESPACE,)):
        err('invalid definition declaration, expected -> after {}'.format(goalname)) 

    rls = rule_list()
    if not rls:
        err('invalid definition body, expected symbols after definition {}'.format(definition.goalname))

    definition.rules = rls
    return definition

def def_list():
    '''
    def_list    = def def_list
                | ddef
    '''
    dprint(1, 'def_list: ',end='')
    defs_list = []
    d = ddef()
    if not d:
        return d
    while d:
        defs_list.append(d)
        d = ddef()
    dprint(1, 'defslist: ', defs_list)
    return defs_list

def grammar():
    '''
    start -> def_list
    '''
    dprint(1, 'grammar: ',end='')
    defs = def_list()
    tkn = TSRC.next_token()
    if not tkn.is_eof():
        err('error, unexpected token: {}'.format(tkn))
    if DEBUG:
        print(defs)
    if not defs:
        raise ValueError('no dlist')
    return defs

'''
End of the top down parser
'''

def mk_symbol(name, ttype, value):
    symbol = nms()
    symbol.name = name
    symbol.ttype = ttype
    symbol.val = value
    return symbol

class symbol_table:
    def __init__(self):
        self.syms = {}
        self.literals = {}
    def __iter__(self):
        yield from self.syms.values()

    def get_symbol(self, name):
        return self.syms.get(name,None)
    def add_symbol(self, symbol):
        if symbol.name in self.syms:
            raise KeyError('symbol {} already exists'.format(symbol.name))
        self.syms[symbol.name] = symbol
        return symbol
    def add_if_uniq(self, symbol):
        if symbol.name in self.syms:
            return self.syms[symbol.name]
        return self.add_symbol(symbol)
    def get_literal(self, pattern):
        if pattern in self.literals:
            return self.literals[pattern]
        name = 'T_LITERAL_{}'.format(len(self.literals))
        sym = mk_symbol(name, R_TERM, pattern)
        self.literals[pattern] = sym
        return self.add_symbol(sym)
    def special_symbol(self, name):
        sym = self.get_symbol(name)
        if sym is not None:
            return sym
        sym = mk_symbol(name, None, None)
        self.add_symbol(sym)
        return sym


def extract_bnf(ast):
    syms = symbol_table()
    productions = {}
    for definition in ast:
        lhs = definition.goalname.val
        rhs = []
        for sequence,arbcode in definition.rules:
            seq = []
            for token in sequence:
                sym = None
                if token.tid == T_IDENTIFER:
                    sym = syms.add_if_uniq(mk_symbol(token.val, R_NONTERM, None))
                elif token.tid == T_T_IDENTIFER:
                    sym = syms.add_if_uniq(mk_symbol(token.val, R_TERM, None))
                elif token.tid == T_LITERAL:
                    sym = syms.get_literal(token.val)
                else:
                    err('unknown token type: {}, {}'.format(token.val, global_rep(token.tid)))
                seq.append(sym)
            rule = nms() 
            rule.arbcode = arbcode
            rule.seq = seq
            rule.lhs = lhs
            syms.add_if_uniq(mk_symbol(lhs, R_NONTERM, None))
            rhs.append(rule)

        if lhs in productions:
            target = productions[lhs]
            target.rules.extend(rhs)
        else:
            productions[lhs] = nms()
            productions[lhs].lhs = lhs
            productions[lhs].rules = rhs

    if '_START' not in productions:
        raise ValueError('no start rule, start rule must be literally: _START -> symbol _END\n(symbol can be any production)')
    start_rl = productions['_START']
    if  (len(start_rl.rules) != 1) or\
        (len(start_rl.rules[0].seq) != 2) or \
        (start_rl.rules[0].seq[1].name != '_END'):
        raise ValueError('start rule must have one target with one token followed by a literal: _END')
    bnf = nms()
    bnf.productions = productions
    bnf.syms = syms
    return bnf

def create_states(bnf):
    ctx = nms()
    ctx.states = []
    ctx.items = None
    ctx.bnf = bnf
    dprint(1, pretty_productions(bnf.productions))

    product = ctx.bnf.productions['_START'].rules[0]
    start_rptr = mk_rptr(rule=product, index=0)
    
    start_item = mk_item([start_rptr], ctx)
    dprint(1,'start item:')
    dprint(1,pretty_item(start_item))
    items = extract_items(start_item, ctx)
    ctx.items = items
    return ctx


def mk_rptr(rule, index):
    '''
    rule pointer
    an rptr is an object containing a reference to a rule and an index into it
    for example suppose we have X -> Y0 Y1 Y2 ...
    these are examples of how different rptrs can refer to a position in it

    rptr .rule=X, .index=0
    X -> • Y0 Y1     Y2 
    rptr .rule=X, .index=1
    X ->   Y0 • Y1   Y2 
    rptr .rule=X, .index=2
    X ->   Y0   Y1 • Y2 
    rptr .rule=X, .index=3
    X ->   Y0   Y1   Y2 •
    '''
    rptr = nms()
    rptr.rule = rule
    rptr.index = index
    rptr.visited = False
    return rptr

def rptr_first_symbol(rptr):
    if rptr.index >= len(rptr.rule.seq):
        return None
    return rptr.rule.seq[rptr.index]

def rptr_prev_symbol(rptr):
    if rptr.index <= 0:
        return None
    return rptr.rule.seq[rptr.index-1]


def iter_rules(productions):
    for p in productions.values():
        yield from p.rules

def mk_item(rptrs, ctx):
    '''
    an item is a collection of rule pointers (.rptrs)
    it is more general than a state, but it can be turned into a state
    this function expands the given rptr into an item
    '''
    dprint(1, 'mk_item() got: ')
    for rptr in rptrs:
        dprint(1, '   ', pretty_rptr(rptr))
        pass
    item = nms()
    item.rptrs = []
    item.rptrs.extend(rptrs)
    #the production targets it already contains expanded, (to avoid readding them)
    item.has = set()
    item.goto = dict()
    item.on = '?'
    done = False
    while not done:
        done = True
        for rptr in item.rptrs:
            if rptr.index < len(rptr.rule.seq):
                token = rptr.rule.seq[rptr.index]
                if token.name in item.has:
                    continue
                for rule in iter_rules(ctx.bnf.productions):
                    if rule.lhs == token.name:
                        # 0 is the index into the rule, all of what we add starts at the beginning
                        item.rptrs.append(mk_rptr(rule, 0)) 
                        item.has.update([token.name])
                        done = False
    dprint(1, 'mk_item() produced: ')
    dprint(1, indent(pretty_item(item),4))
    return item


def rptr_identity(rptr):
    '''
    a value that we can use to decide whether two rptrs are equivalent
    '''
    return (id(rptr.rule) * rptr.index)

def item_identity(item):
    '''
    a value that we can use to decide whether two items are equivalent
    '''
    h = list()
    item.rptrs.sort(key=rptr_identity)
    for r in item.rptrs:
        h.append(rptr_identity(r))
    return tuple(h)

def item_index(item, item_list):
    '''
    find an equivalent of item in item_list
    returns an index or -1
    '''
    item_id = item_identity(item)
    for i,litem in enumerate(item_list):
        if item_identity(litem) == item_id:
            return i
    return -1



def extract_items(start_item, ctx):
    '''
    given a start_item and a ctx (grammar context)
    returns all states reachable (a list that will include the start_item)
    '''
    states =  [start_item]
    done = False
    while not done:
        done = True
        for state in states:
            for sym in ctx.bnf.syms.syms:
                if sym in state.goto:
                    continue
                relevant_rptrs = []
                for rptr in state.rptrs:
                    #even something that points to the end is accepted
                    if rptr.index >= len(rptr.rule.seq):
                        continue
                    cur_sym = rptr.rule.seq[rptr.index].name
                    if cur_sym != sym:
                        continue
                    nrptr = mk_rptr(rptr.rule, rptr.index+1)
                    relevant_rptrs.append(nrptr)
                if not relevant_rptrs:
                    continue
                done = False
                item = mk_item(relevant_rptrs, ctx)
                item.on = sym
                item_idx = item_index(item, states)
                if item_idx != -1:
                    dprint(1, 'original: ', pretty_item(states[item_idx]))
                    dprint(1, 'new: ', pretty_item(item))
                    #state is not new
                    state.goto[sym] = states[item_idx]
                else:
                    state.goto[sym] = item
                    states.append(item)
                dprint(1, '\n\n',pretty_item(item),'\n\n')
    return states

'''
note about first and follow
for some languages those arent defined (read 'recursive descent vs lalr' a post in google groups)
(these are languages that require backtracking)
'''

def update_first(first_dict, sym, ctx):
    changed = False
    #is a terminal
    if sym.name not in ctx.bnf.syms:
        changed = sym.name not in first_dict
        first_dict[sym.name] = set([sym.name]) #terminals have themselves in their first() set
    else:
        first_dict[sym.name] = set()
        for rule in ctx.bnf.productions[sym.name].rules:
            for i,rsym in enumerate(rule.seq):
                if rsym.name not in first_dict:
                    changed = True
                    update_first(first_dict, rsym, ctx)
                first_dict[sym.name] |= (first_dict[rsym.name] - set(['_EPSILON']))
                if '_EPSILON' in first_dict[rsym.name]:
                    #if its the last then we add epsilon (this implies all of X-> Y0,Y1,Yk have epsilon, so X has epsilon too)
                    if rsym is rule.seq[-1]:
                        first_dict[sym] |= set(['_EPSILON'])
                else:
                    break
    return changed


def generate_first(ctx):
    '''
    returns a dictionary mapping: symbol -> [first_set]
    '''
    first = {}
    changed = True
    while changed:
        changed = False
        for sym in ctx.bnf.syms:
            changed = changed or update_first(first, sym, ctx)
    return first

def update_follow(follow,first, sym, ctx):
    changed = False
    for rule in iter_rules(ctx.bnf.productions):
        all_had_epsilon = True
        for i,sym in enumerate(rule.seq):
            if sym.ttype == R_TERM:
                follow[sym.name] = set()
            elif not sym.name in follow:
                follow[sym.name] = set()
            if (len(rule.seq) - i - 1) > 0: # there is something ahead of current sym
                #add the next sym's first() to this sym's follow()
                if sym.ttype == R_NONTERM:
                    nsym = rule.seq[i+1]
                    follow[sym.name] |= (first[nsym.name] - set(['_EPSILON']))
            if '_EPSILON' not in first[sym.name]:
                all_had_epsilon = False

            if sym is rule.seq[-1]:
                #if lhs -> 
                fsym  = sym
                if '_EPSILON' in first[fsym.name]:
                    if i > 0:
                        psym = rule.seq[i-1]
                        if '_EPSILON' in first[psym.name]:
                            raise ValueError('multiple possibly empty syms in the end of rule {}'.format(rule))
                        follow[psym.name] |= first[rule.lhs]
                else:
                    if fsym.ttype == R_NONTERM and fsym.name not in ['_END']:
                        if fsym.name not in follow:
                            follow[fsym.name] = set()
                        dprint(2,'add all of {} follow() to {} follow()'.format(rule.lhs, fsym.name))
                        follow[fsym.name] |= follow[rule.lhs] 
    return changed

def generate_follow(first, ctx):
    '''
        returns a dictionary mapping: symbol -> [follow_set]
    '''
    follow = {}
    changed = True
    follow['_START'] = set(['_END'])
    while changed:
        changed = False
        for sym in ctx.bnf.syms:
            changed = changed or update_follow(follow, first, sym, ctx)
    return follow

def mk_slr_entry(action_type, number=None):
    '''
    make an entry
    examples:
        mk_slr_entry(None)
        mk_slr_entry(EA_SHIFT, 3)
        mk_slr_entry(EA_GOTO, 0)
    '''
    entry = nms()
    if action_type is None:
        action_type = EA_NONE
    if action_type not in EA_ACTIONS:
        raise ValueError('unknown action type: {}'.format(global_rep(action_type)))
    entry.action  = action_type
    entry.number = number
    return entry

def slr_entry_equ(lhs, rhs):
    return (lhs.action == rhs.action) and (rhs.number == lhs.number)

def slr_table_action_conflict(symbol_literal, taken_action, new_action):
    err(('Action conflict, entry on symbol {}: {}\n' + \
        'is in conflict with the entry: {}').format(symbol_literal,
                                                    pretty_slr_entry(taken_action),
                                                    pretty_slr_entry(new_action)))

def generate_slr_table(ctx):
    '''
    the algorithm can be found in page 253, in the dragon book
    '''
    states = ctx.items #contains .items:(rptrs to rules)
    #rows are state indices, columns are gotos based on symbols
    index_to_symbol  = []
    index_to_state   = []
    index_to_rule    = []

    #sets of literal symbols (rather than token refernces,
    #they're guarenteed to be unique, we can use the symbol table to get the original token reference)
    first = generate_first(ctx)
    follow = generate_follow(first, ctx)

    ctx.bnf.syms.special_symbol('_START')
    end_symbol = ctx.bnf.syms.special_symbol('_END')

    for i,state in enumerate(states):
        state.state_num = i
        index_to_state.append(state)
    for i,s in enumerate(ctx.bnf.syms):
        s.sym_num = i
        index_to_symbol.append(s)
    for i,r in enumerate(iter_rules(ctx.bnf.productions)):
        r.rule_num = i
        index_to_rule.append(r)

    rows = []
    for state_num,state in enumerate(index_to_state):
        row = [None for i in range(len(index_to_symbol))]
        for symbol_num,symbol in enumerate(index_to_symbol):
            #current symbol's action, can only have 1
            taken_action = None

            goto_target = None
            if symbol.name in state.goto:
                goto_target = state.goto[symbol.name].state_num
            #nonterminal
            if symbol.name in ctx.bnf.productions:
                if goto_target:
                    row[symbol_num] = mk_slr_entry(EA_GOTO, goto_target)
                continue
            #find in what rptrs does the symbol appear and follow the algorithm rules
            for rptr in state.rptrs:
                #check for algorithm rule 1.
                if symbol.name in state.goto:
                    first_symbol = rptr_first_symbol(rptr) 
                    if first_symbol and first_symbol.name == symbol.name: # lhs -> • rptr A B
                        new_action =  mk_slr_entry(EA_SHIFT, goto_target)
                        if goto_target < 0:
                            #raise ValueError()
                            pass
                        if (taken_action is not None) and not slr_entry_equ(new_action, taken_action):
                            slr_table_action_conflict(symbol.name, taken_action, new_action)
                        row[symbol_num] = new_action
                if (rptr_first_symbol(rptr) is None) and rptr_prev_symbol(rptr): # lhs -> A B rptr •
                    #rule 3.
                    if rptr.rule.lhs == '_START':
                        row[end_symbol.sym_num] = mk_slr_entry(EA_ACC, EA_ACC)
                    else:
                        #rule 2 
                        for follower_symbol_name in follow[rptr.rule.lhs]:
                            follower_index = ctx.bnf.syms.get_symbol(follower_symbol_name).sym_num
                            new_action = mk_slr_entry(EA_REDUCE, rptr.rule.rule_num)
                            if (row[follower_index] is not None) and not slr_entry_equ(new_action, row[follower_index]):
                                slr_table_action_conflict(follower_symbol, row[follower_index], new_action)
                            row[follower_index] = new_action
        rows.append(row)

    table = nms()
    table.rows = rows
    table.index_to_state  = index_to_state
    table.index_to_symbol = index_to_symbol
    table.index_to_rule = index_to_rule
    table.ctx = ctx
    return table



def dprint(when, *args, **kwargs):
    if when <= DEBUG:
        print(*args, **kwargs)

        
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
    dprint(1, 'DEBUG: ',DEBUG)
    return args


def main():
    global TSRC

    args = parse_cmd_line_args()
    input_str = open(args['in']).read()
    TSRC = token_source(input_str)
    
    ast = grammar() #returns a tree like dictionary (nested SimpleNamespace)
    bnf = extract_bnf(ast)
    ctx = create_states(bnf)

    for i in ctx.items:
        dprint(1, pretty_item(i))
        dprint(2, pretty_item_goto(i))
    first = generate_first(ctx)
    follow = generate_follow(first, ctx)
    dprint(1, 'first:')
    dprint(1, indent(pretty_first_or_last(first),4))
    dprint(1, 'follow:')
    dprint(1, indent(pretty_first_or_last(follow),4))
    table = generate_slr_table(ctx)
    dprint(1, pretty_slr_table(table, 8))



if __name__ == '__main__':
    main()
