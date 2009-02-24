#!/usr/bin/python
import Tkinter
import tkFileDialog
import Image
import ImageTk
import ImageFilter
import ImageDraw
import sys
import os
import signal
import math
import subprocess
import time

def _(s): return s  # TODO: i18n

app = Tkinter.Tk()
app.wm_title(_("CropGUI -- lossless cropping and rotation of jpeg files"))
app.wm_iconname(_("CropGUI"))

preview = Tkinter.Label(app)
do_crop = Tkinter.Button(app, text="Crop")
info = Tkinter.Label(app)
preview.pack(side="bottom")
do_crop.pack(side="left")
info.pack(side="left")

(   
    DRAG_NONE,
    DRAG_TL, DRAG_T, DRAG_TR,
    DRAG_L,  DRAG_C, DRAG_R,
    DRAG_BL, DRAG_B, DRAG_BR
) = range(10)

def clamp(value, low, high):
    if value < low: return low
    if high < value: return high
    return value

class DragManager(object):
    def __init__(self, w, b=None, inf=None):
        self.l = w
        if b: b.configure(command=self.done)
        self.inf = inf
        w.bind("<Button-1>", self.start)
        w.bind("<Double-Button-1>", self.start)
        w.bind("<Button1-Motion>", self.motion)
        w.bind("<ButtonRelease-1>", self.end)
        dummy_image = Image.fromstring('RGB', (1,1), '\0\0\0')
        self.dummy_tkimage = ImageTk.PhotoImage(dummy_image)
        self.state = DRAG_NONE
        self.round = 1
        self.image = None
        self.handle_size = 0
        w.configure(image=self.dummy_tkimage)
        self.v = Tkinter.BooleanVar(app)

    def get_w(self): return self.image.size[0]
    w = property(get_w)
    def get_h(self): return self.image.size[1]
    h = property(get_h)

    def set_image(self, image):
        if image is None:
            if hasattr(self, 'left'): del self.left
            if hasattr(self, 'right'): del self.right
            if hasattr(self, 'bottom'): del self.bottom
            if hasattr(self, 'blurred'): del self.blurred
            if hasattr(self, 'xor'): del self.xor
            if hasattr(self, 'tkimage'): del self.tkimage
            self._image = None
        else:
            self._image = image.copy()
            self.top = 0
            self.left = 0
            self.right = self.w
            self.bottom = self.h
            mult = len(self.image.mode)
            self.blurred = image.copy().filter(
                ImageFilter.SMOOTH_MORE).point([x/2 for x in range(256)] * mult)
            self.xor = image.copy().point([x ^ 128 for x in range(256)] * mult)
        self.render()

    def fix(self, a, b, lim):
        a = clamp(a, 0, lim) * 1. / self.round
        b = clamp(b, 0, lim) * 1. / self.round
        if b < a: a, b = b, a
        a = int(math.floor(a)*self.round)
        b = int(math.ceil(b)*self.round)
        ## if image is not a multiple of round, b could end up greater than lim
        return a, min(b, lim)

    def set_crop(self, top, left, right, bottom):
        self.top, self.bottom = self.fix(top, bottom, self.h)
        self.left, self.right = self.fix(left, right, self.w)
        self.render()

    def get_image(self):
        return self._image
    image = property(get_image, set_image, None,
                "change the target of this DragManager")

    def render(self):
        if self.image is None:
            self.l.configure(image=self.dummy_tkimage)
            return

        mask = Image.new('1', self.image.size, 0)
        mask.paste(1, (self.left, self.top, self.right, self.bottom))
        image = Image.composite(self.image, self.blurred, mask)

        t, l, r, b = self.top, self.left, self.right, self.bottom
        dx = (r - l) / 4
        dy = (b - t) / 4

        if self.inf:
            self.inf.configure(text=
                "Left:  %4d  Top:    %4d\n"
                "Right: %4d  Bottom: %4d\n"
                "Width: %4d  Height: %4d\n"
                "State: %s" % (l, t, r, b, r-l, b-t, self.state),
                font="fixed")

        mask = Image.new('1', self.image.size, 1)
        draw = ImageDraw.Draw(mask)

        draw.line([l, t, r, t], fill=0)
        draw.line([l, b, r, b], fill=0)
        draw.line([l, t, l, b], fill=0)
        draw.line([r, t, r, b], fill=0)

        draw.line([l+dx, t, l+dx, t+dy, l, t+dy], fill=0)
        draw.line([r-dx, t, r-dx, t+dy, r, t+dy], fill=0)
        draw.line([l+dx, b, l+dx, b-dy, l, b-dy], fill=0)
        draw.line([r-dx, b, r-dx, b-dy, r, b-dy], fill=0)

        image = Image.composite(image, self.xor, mask)
        self.tkimage = ImageTk.PhotoImage(image)
        self.l.configure(image=self.tkimage)

    def enter(self, event):
        pass
    def leave(self, event):
        pass

    def classify(self, x, y):
        t, l, r, b = self.top, self.left, self.right, self.bottom
        dx = (r - l) / 4
        dy = (b - t) / 4

        print x, l, r, dx, x<l, x<l+dx, x<r-dx, x<r
        print y, t, b, dy, y<t, y<t+dy, y<b-dy, y<b

        if x < l: return DRAG_NONE
        if x > r: return DRAG_NONE
        if y < t: return DRAG_NONE
        if y > b: return DRAG_NONE

        if x < l+dx:
            if y < t+dy: return DRAG_TL
            if y < b-dy: return DRAG_L
            return DRAG_BL
        if x < r-dx:
            if y < t+dy: return DRAG_T
            if y < b-dy: return DRAG_C
            return DRAG_B
        else:
            if y < t+dy: return DRAG_TR
            if y < b-dy: return DRAG_R
            return DRAG_BR

    def start(self, event):
        self.x0 = event.x
        self.y0 = event.y
        self.state = self.classify(event.x, event.y)
        print "start", self.state

    def motion(self, event):
        dx = event.x - self.x0; self.x0 = event.x
        dy = event.y - self.y0; self.y0 = event.y
        new_top, new_left, new_right, new_bottom = \
            self.top, self.left, self.right, self.bottom
        if self.state == DRAG_C:
            # A center drag bumps into the edges
            if dx > 0:
                dx = min(dx, self.right - self.w)
            else:
                dx = max(dx, -self.left)
            if dy > 0:
                dy = min(dx, self.bottom - self.h)
            else:
                dy = max(dx, -self.top)
        if self.state in (DRAG_TL, DRAG_T, DRAG_TR, DRAG_C):
            new_top = self.top + dy
        if self.state in (DRAG_TL, DRAG_L, DRAG_BL, DRAG_C):
            new_left = self.left + dx
        if self.state in (DRAG_TR, DRAG_R, DRAG_BR, DRAG_C):
            new_right = self.right + dx
        if self.state in (DRAG_BL, DRAG_B, DRAG_BR, DRAG_C):
            new_bottom = self.bottom + dy
        # A drag never moves left past right and so on
        new_top = min(self.bottom, new_top)
        new_left = min(self.right, new_left)
        new_right = max(self.left, new_right)
        new_bottom = max(self.top, new_bottom)

        self.set_crop(new_top, new_left, new_right, new_bottom)

    def end(self, event):
        self.state = DRAG_NONE

    def done(self):
        self.v.set(1)

    def double(self, event):
        self.done()

    def wait(self):
        app.wait_variable(self.v)




max_h = app.winfo_screenheight() - 64 - 32
max_w = app.winfo_screenwidth() - 64

drag = DragManager(preview, do_crop, info)

def image_names():
    if len(sys.argv) > 1:
        for i in sys.argv[1:]: yield i
    else:
        while 1:
            names = tkFileDialog.askopenfilenames(master=app,
                defaultextension=".jpg", multiple=1, parent=app,
                filetypes=(
                    (_("JPEG Image Files"), ".jpg .JPG .jpeg .JPEG"),
                    (_("All files"), "*"),
                ),
                title=_("Select images to crop"))
            print repr(names)
            if not names: break
            for name in names: yield name

pids = set()
def reap():
    global pids
    pids = set(p for p in pids if p.poll() is None)

for image_name in image_names():
    i = Image.open(image_name)
    iw, ih = i.size
    scale=1
    while iw > max_w or ih > max_h:
        iw /= 2
        ih /= 2
        scale *= 2
    i.thumbnail((iw, ih))
    drag.image = i
    drag.round = max(1, 8/scale)
    drag.wait()
    
    base, ext = os.path.splitext(image_name)
    t, l, r, b = drag.top, drag.left, drag.right, drag.bottom
    t *= scale
    l *= scale
    r *= scale
    b *= scale
    cropspec = "%dx%d+%d+%d" % (r-l, b-t, l, t)
    target = base + "-crop" + ext
    print "crop", image_name, target, cropspec
    target = open(target, "wb")
    pids.add(subprocess.Popen(
        ['jpegtran','-optimize','-progressive','-crop',cropspec,image_name],
        stdout=target))
    target.close()

while pids:
    reap()
    sys.stdout.write("Waiting for %d children to exit.   \r" % len(pids))
    sys.stdout.flush()
    time.sleep(.1)

# 1. open image
# 2. choose 1/2, 1/4, 1/8 scaling so that resized image fits onscreen
# 3. load image at requested size
# 4. run GUI to get desired crop settings
# 5. write output file
