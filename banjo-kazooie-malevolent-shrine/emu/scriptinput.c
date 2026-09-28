// Minimal mupen64plus input plugin that replays a scripted button timeline.
// Script (env M64_INPUT_SCRIPT): lines "start end BUTTONS [x y]", frames = GetKeys(0) calls.
#define M64P_PLUGIN_PROTOTYPES 1
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "m64p_types.h"
#include "m64p_plugin.h"

typedef struct { long s, e; unsigned buttons; int x, y; } Step;
static Step steps[4096]; static int nsteps; static long frame; static FILE *logf;

static unsigned parse_buttons(const char *t) {
    unsigned v = 0; char buf[256]; strncpy(buf, t, 255); buf[255]=0;
    for (char *p = strtok(buf, "+"); p; p = strtok(NULL, "+")) {
        if (!strcmp(p,"A")) v |= 1u<<7; else if (!strcmp(p,"B")) v |= 1u<<6;
        else if (!strcmp(p,"Z")) v |= 1u<<5; else if (!strcmp(p,"START")) v |= 1u<<4;
        else if (!strcmp(p,"DU")) v |= 1u<<3; else if (!strcmp(p,"DD")) v |= 1u<<2;
        else if (!strcmp(p,"DL")) v |= 1u<<1; else if (!strcmp(p,"DR")) v |= 1u<<0;
        else if (!strcmp(p,"CR")) v |= 1u<<8; else if (!strcmp(p,"CL")) v |= 1u<<9;
        else if (!strcmp(p,"CD")) v |= 1u<<10; else if (!strcmp(p,"CU")) v |= 1u<<11;
        else if (!strcmp(p,"R")) v |= 1u<<12; else if (!strcmp(p,"L")) v |= 1u<<13;
    }
    return v;
}

EXPORT m64p_error CALL PluginStartup(m64p_dynlib_handle h, void *ctx, void (*dbg)(void *, int, const char *)) {
    const char *path = getenv("M64_INPUT_SCRIPT");
    const char *lp = getenv("M64_INPUT_LOG");
    if (lp) logf = fopen(lp, "w");
    if (path) {
        FILE *f = fopen(path, "r"); char line[512];
        while (f && fgets(line, sizeof line, f) && nsteps < 4096) {
            Step st = {0}; char b[256] = "-";
            if (line[0]=='#' || line[0]=='\n') continue;
            int n = sscanf(line, "%ld %ld %255s %d %d", &st.s, &st.e, b, &st.x, &st.y);
            if (n >= 3) { st.buttons = parse_buttons(b); steps[nsteps++] = st; }
        }
        if (f) fclose(f);
    }
    return M64ERR_SUCCESS;
}
EXPORT m64p_error CALL PluginShutdown(void) { if (logf) fclose(logf); return M64ERR_SUCCESS; }
EXPORT m64p_error CALL PluginGetVersion(m64p_plugin_type *t, int *v, int *api, const char **name, int *caps) {
    if (t) *t = M64PLUGIN_INPUT; if (v) *v = 0x010000; if (api) *api = 0x020100;
    if (name) *name = "scriptinput"; if (caps) *caps = 0; return M64ERR_SUCCESS;
}
EXPORT void CALL InitiateControllers(CONTROL_INFO ci) {
    for (int i = 0; i < 4; i++) { ci.Controls[i].Present = (i == 0); ci.Controls[i].RawData = 0; ci.Controls[i].Plugin = PLUGIN_NONE; }
}
EXPORT void CALL GetKeys(int c, BUTTONS *k) {
    k->Value = 0;
    if (c != 0) return;
    unsigned v = 0; int x = 0, y = 0;
    for (int i = 0; i < nsteps; i++)
        if (frame >= steps[i].s && frame < steps[i].e) { v |= steps[i].buttons; if (steps[i].x || steps[i].y) { x = steps[i].x; y = steps[i].y; } }
    k->Value = v & 0xFFFF;
    k->X_AXIS = x; k->Y_AXIS = y;
    if (logf && (frame % 30 == 0)) { fprintf(logf, "%ld\n", frame); fflush(logf); }
    frame++;
}
EXPORT void CALL ControllerCommand(int c, unsigned char *cmd) {}
EXPORT void CALL ReadController(int c, unsigned char *cmd) {}
EXPORT int  CALL RomOpen(void) { return 1; }
EXPORT void CALL RomClosed(void) {}
EXPORT void CALL SDL_KeyDown(int m, int s) {}
EXPORT void CALL SDL_KeyUp(int m, int s) {}
EXPORT void CALL RenderCallback(void) {}
