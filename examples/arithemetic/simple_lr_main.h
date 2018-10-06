
int main(int argc, const char **argv)
{
    int top;
    int rule_num;
    int lhs; //left hand side of a rule

    struct parse_info_s pr = {0}; //all indices should be 0
    pr.symbol_stack.idx = 0;
    pr.state_stack.idx = 0;
    top = 0;
    pr.next_input = next_input();
    while (1){
        top = pr.state_stack.data[pr.state_stack.idx].state;


        //safety checks :)
        if (top > STACKLEN){
#ifdef DBG_PRINT
            printf("top %d, %s, exiting\n", top, represent(top));
#endif
            exit(1);
        }
        if (pr.next_input > SYMBOLSMAX){
#ifdef DBG_PRINT
            printf( "input: %d, %s, exiting\n",
                    top,
                    represent(pr.next_input));
#endif
            exit(1);
        }

        if (states[top].actions[pr.next_input].action == EA_SHIFT){
#ifdef DBG_PRINT
            printf("at state: %3d, shifting state %3d, according to symbol: %s, stidx: %d, syidx: %d\n", top,
                                                                                   states[top].actions[pr.next_input].target,
                                                                                   represent(pr.next_input),
                                                                                   pr.state_stack.idx,
                                                                                   pr.symbol_stack.idx);
                                                                                   
#endif
            pr.symbol_stack.data[++pr.symbol_stack.idx].input = pr.next_input;
            pr.state_stack.data[++pr.state_stack.idx].state = states[top].actions[pr.next_input].target;
            pr.next_input = next_input();
        }
        else if(states[top].actions[pr.next_input].action == EA_REDUCE){
#ifdef DBG_PRINT
                printf( "at state: %3d, reducing by rule: %3d, according to symbol: %s, stidx: %d, syidx: %d\n",
                        top,
                        states[top].actions[pr.next_input].target,
                        represent(pr.next_input),
                        pr.state_stack.idx,
                        pr.symbol_stack.idx);
#endif

            state_stack_pushpop(&pr); 
            top = pr.state_stack.data[pr.state_stack.idx].state;
            /* if (pr.next_input == _END) */
            /*     goto END; */
        }
        else{
            if(states[top].actions[pr.next_input].action == EA_ACC){
                accept(&pr);
                return 0;
            }
            else if(states[top].actions[pr.next_input].action == EA_REJ){
                reject(&pr);
                return 1;
            }
#ifdef DBG_PRINT
            printf("(action %s), at state: %3d, next_input = %s\nunknown action, exiting\n", represent(states[top].actions[pr.next_input].action),
                                                                                top, 
                                                                                represent(pr.next_input));
#endif
            return 1;
        }
    }

END:



    printf("\ndone\n");
}
