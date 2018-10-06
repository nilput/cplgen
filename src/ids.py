
def generate_int(set_to=None):
    ''' generate an integer and increment a global variable, used to create an enum '''
    global I_COUNT
    I_COUNT += 1
    if set_to is not None:
        I_COUNT = set_to
    return I_COUNT

def global_rep(I):
    '''
        given the value of a global variable it returns it as a string
        (used for debugging, the value has to be unique)
    '''
    for k,v in globals().items():
        if v == I:
            return k
    return str(I)


I_COUNT = 0


T_WHITESPACE   = generate_int(1000)
T_NEWL         = generate_int()
T_COMMENT      = generate_int()
T_IDENTIFER    = generate_int()
T_T_IDENTIFER  = generate_int()
T_LITERAL      = generate_int()
T_DRV_SYMBOL   = generate_int()
T_OR_SYMBOL    = generate_int()
T_ARB_CODE     = generate_int()
T_END          = generate_int()




'''
R_ prefixed stuff are for the target grammar (instead of T_ prefixed that are used in that parser generator)
'''

R_TERM       = generate_int()
R_NONTERM    = generate_int()
R_UNKNOWN_ID = generate_int()


EA_SHIFT  = generate_int(4000)
EA_REDUCE = generate_int()
EA_GOTO   = generate_int()
EA_ACC   = generate_int()
EA_REJ   = generate_int()
EA_NONE   = generate_int()
EA_ACTIONS = [EA_SHIFT, EA_REDUCE, EA_GOTO, EA_NONE,  EA_REJ, EA_ACC]
