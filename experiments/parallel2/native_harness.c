// Native ARM64 tests execute the exact hook bodies, with test far-jump exits.
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct Task {
    uint8_t prefix[0x58];
    uint8_t active, audio;
    uint8_t pad[2];
    uint32_t state;
    int ready, done, starts, pending;
} Task;
typedef struct Ref { Task *ptr; void *owner; } Ref;
typedef struct Helper {
    uint8_t prefix[0x78];
    Ref *begin, *end, *capacity;
} Helper;
extern int test_scheduler(Helper *, Ref *, Ref *);
extern int test_admission(Helper *, Task *);
_Static_assert(offsetof(Task, active)==0x58, "active offset");
_Static_assert(offsetof(Task, audio)==0x59, "audio offset");
_Static_assert(offsetof(Task, state)==0x5c, "state offset");
_Static_assert(offsetof(Helper, begin)==0x78, "video vector offset");
_Static_assert(sizeof(Ref)==16, "shared_ptr slot size");

static unsigned checks;
static int active(Helper *h) {
    int n=0;
    for (Ref *r=h->begin;r<h->end;++r) n += r->ptr->active!=0;
    return n;
}
static void init(Helper *h,Ref *refs,Task *tasks,int n) {
    memset(h,0,sizeof(*h));memset(tasks,0,n*sizeof(*tasks));
    h->begin=refs;h->end=refs+n;h->capacity=refs+n;
    for(int i=0;i<n;++i) {refs[i]=(Ref){tasks+i,0};tasks[i].ready=1;tasks[i].pending=1;}
}
static void exhaustive_leaf_tests(void) {
    Helper h;Ref refs[8];Task t[8];
    for(int n=1;n<=8;++n)for(unsigned mask=0;mask<(1u<<n);++mask) {
        init(&h,refs,t,n);
        for(int i=0;i<n;++i)t[i].active=(mask>>i)&1;
        int before=active(&h);
        for(int i=0;i<n;++i) {
            int expected=before>=2?0:(t[i].active?2:1);
            assert(test_scheduler(&h,refs+i,h.end)==expected);++checks;
            uint8_t old=t[i].active;
            int admit=before<2 && !old;
            assert(test_admission(&h,t+i)==admit);++checks;
            assert(t[i].active==(admit?1:old));
            if(admit)assert(t[i].state==3);
            t[i].active=old;t[i].state=0;
            // Audio behavior stays independent of the video queue's count.
            t[i].audio=1;
            assert(test_scheduler(&h,refs+i,h.end)==(old?0:1));++checks;
            assert(test_admission(&h,t+i)==1);++checks;
            t[i].active=old;t[i].audio=0;t[i].state=0;
        }
    }
    // Count nonzero active bytes, rather than assuming only byte value1.
    init(&h,refs,t,3);t[0].active=7;t[1].active=255;
    assert(test_scheduler(&h,refs+2,h.end)==0);
    assert(test_admission(&h,t+2)==0);checks+=2;
}

// Exercise native leaf admission in a scheduler model whose omitted sections
// are the vendor's unchanged readiness and completion/removal behavior.
static void remove_task(Helper *h,Task *t) {
    for(Ref *r=h->begin;r<h->end;++r)if(r->ptr==t){
        memmove(r,r+1,(size_t)(h->end-r-1)*sizeof(*r));--h->end;return;
    }
    assert(0);
}
static Task *schedule(Helper *h,Task *reentrant, int synchronous) {
    for(Ref *r=h->begin;r<h->end;++r) {
        int action=test_scheduler(h,r,h->end);
        if(!action)return 0;
        if(action==2)continue;
        Task *t=r->ptr;
        if(!t->ready){t->state=2;continue;}
        // Emulate a native preflight callback consuming the last slot before
        // the selected task reaches the central active-byte store.
        if(reentrant) {
            if(test_admission(h,reentrant))++reentrant->starts;
            reentrant=0;
        }
        if(test_admission(h,t)) {
            ++t->starts;assert(active(h)<=2);
            if(synchronous) {
                t->active=0;t->done=1;t->pending=0;remove_task(h,t);
                schedule(h,0,0);
            }
            // Like vendor tail-call: never dereference r after doTask.
            return t;
        }
        return 0;
    }
    return 0;
}
static void complete(Helper *h,Task *t) {
    assert(t->active);t->active=0;t->done=1;t->pending=0;
    remove_task(h,t);schedule(h,0,0);assert(active(h)<=2);
}
static void lifecycle_tests(void) {
    Helper h;Ref refs[8];Task t[8];
    init(&h,refs,t,5);t[0].ready=0;
    assert(schedule(&h,0,0)==t+1);
    assert(schedule(&h,0,0)==t+2);assert(active(&h)==2);
    t[0].ready=1;assert(schedule(&h,0,0)==0); // full, blocked-head now ready
    assert(!test_admission(&h,t+3));assert(t[3].pending&&!t[3].active);
    complete(&h,t+1);assert(t[0].active&&active(&h)==2);
    complete(&h,t+2);assert(t[3].active&&active(&h)==2);
    // Failure/cancel take the same unchanged active-clear/remove/reschedule.
    complete(&h,t);assert(t[4].active&&active(&h)==2);
    complete(&h,t+3);complete(&h,t+4);assert(h.begin==h.end);
    for(int i=0;i<5;++i)assert(t[i].starts==1&&t[i].done&&!t[i].pending);
    // Reentrant force start consumes second slot; selected task defers safely.
    init(&h,refs,t,4);assert(schedule(&h,0,0)==t);
    assert(schedule(&h,t+2,0)==0);assert(active(&h)==2);
    assert(t[1].pending&&!t[1].active);complete(&h,t);assert(t[1].active);
    // Duplicate/reentrant request of an already-active same TaskInfo is refused.
    assert(!test_admission(&h,t+1));assert(t[1].starts==1);
    // Synchronous completion removes/reallocates the vector; scheduler does not
    // resume its old iterator after the original tail-call boundary.
    init(&h,refs,t,4);assert(schedule(&h,0,1)==t);
    assert(h.end-h.begin==3&&t[0].done&&t[1].active&&active(&h)==1);
    assert(schedule(&h,0,0)==t+2);assert(active(&h)==2);
    // Two completions/callbacks in succession refill exactly the released slots.
    complete(&h,t+1);assert(active(&h)==2);
    complete(&h,t+2);complete(&h,t+3);assert(h.begin==h.end);
    checks+=31;
}
int main(void) {
    exhaustive_leaf_tests();lifecycle_tests();
    printf("{\"status\":\"passed\",\"native_leaf_checks\":%u,"
           "\"scope\":\"ARM64 hooks plus lifecycle model; not vendor runtime\"}\n",checks);
    return 0;
}
