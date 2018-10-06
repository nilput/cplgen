#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include "data_struct.h" //a user defined struct named pdata_s

struct state_stack_entry_s{
    int state;
};
struct state_stack_s{
    struct state_stack_entry_s data[STACKLEN];
    int idx;
};

struct symbol_stack_s{
    struct pdata_s data[STACKLEN];
    int idx;
};

struct parse_info_s{
    struct state_stack_s state_stack;
    struct symbol_stack_s symbol_stack;
    int next_input;
};

struct action_s{
    int action;
    int target;
};

struct rule_s{
    int rule_length;
    int rule_lhs;
};

struct state_table_s{
    struct action_s actions[SYMBOLSMAX];
};


struct state_table_s states[];
struct rule_s rules_data[];



void reduce_action(struct parse_info_s *p, int rule_num);

static void syntax_error(){
    printf("a syntax error has occured\n");
    exit(1);
}
static void runtime_error(){
    printf("a runtime error has occured\n");
    exit(2);
}


static void state_stack_pushpop(struct parse_info_s *p){
    // adds [new] at the end, executes user action, then gets rid of [...old2, old1], and moves new to where the old rule started

    //the rule we're reducing according to
    int rule_num           = states[p->state_stack.data[p->state_stack.idx].state].actions[p->next_input].target; 
    int production_sym     = rules_data[rule_num].rule_lhs;
    int rule_len           = rules_data[rule_num].rule_length;
    int rule_begin_idx     = p->state_stack.idx - rule_len + 1;
    //the state before the rule's symbols determines where we go next
    if (states[p->state_stack.data[rule_begin_idx - 1].state].actions[production_sym].action != EA_GOTO){
        runtime_error();
    }
    int goto_state = states[p->state_stack.data[rule_begin_idx - 1].state].actions[production_sym].target;
    p->symbol_stack.idx++;
    p->state_stack.data[++p->state_stack.idx].state = goto_state;

    reduce_action(p, rule_num); //modfies whats at p->stack.idx
    if (rule_len > 0){
        //overwrite whats after prev_top
        memcpy(p->state_stack.data + rule_begin_idx, p->state_stack.data + p->state_stack.idx, sizeof(struct state_stack_entry_s)); 
        memcpy(p->symbol_stack.data + rule_begin_idx, p->symbol_stack.data + p->symbol_stack.idx, sizeof(struct pdata_s)); 
        p->state_stack.idx  = rule_begin_idx;
        p->symbol_stack.idx = rule_begin_idx;
    }
}


static void accept(struct parse_info_s *p){
    printf("accepted\n");
    exit(0);
}

static void reject(struct parse_info_s *p){
    printf("rejected\n");
    exit(1);
}
