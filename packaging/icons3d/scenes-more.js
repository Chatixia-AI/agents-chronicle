// ---------- the open Knowledge book, as in filing.html (glow handles only)
function makeBook() {
  const { glossy, std, mesh, roundBox } = CAST.parts;
  const g = new THREE.Group(), mats = [];
  const cover = glossy('#4FC9A8'), paper = std('#FBF6EC', { roughness: .6 });
  [-1, 1].forEach((side) => {
    const half = new THREE.Group();
    const c = mesh(roundBox(1.25, 1.7, .08, .08, .03), cover); c.rotation.x = -Math.PI / 2; c.position.set(side * .64, 0, .85); half.add(c);
    const pages = mesh(roundBox(1.12, 1.56, .16, .03, .02), paper); pages.rotation.x = -Math.PI / 2; pages.position.set(side * .6, .1, .78); half.add(pages);
    const cv = document.createElement('canvas'); cv.width = 256; cv.height = 358; const x = cv.getContext('2d');
    const cols = side < 0 ? ['#2F7FD0', '#5D86B6', '#5D86B6', '#E8902A', '#5D86B6', '#5D86B6', '#22A884'] : ['#7458E0', '#5D86B6', '#5D86B6', '#5D86B6', '#2F7FD0', '#5D86B6', '#5D86B6'];
    cols.forEach((col, i) => { x.fillStyle = col; const wd = i === 0 ? .5 : [.82, .74, .86, .6, .78, .7][(i + (side > 0 ? 2 : 0)) % 6];
      x.beginPath(); x.roundRect(256 * .06, 358 * (.08 + i * .125), 256 * wd, 358 * (i === 0 ? .06 : .04), 358 * .02); x.fill(); });
    const tex = new THREE.CanvasTexture(cv); tex.encoding = THREE.sRGBEncoding;
    const m = new THREE.MeshStandardMaterial({ map: tex, emissive: '#8fd0ff', emissiveMap: tex, emissiveIntensity: 0, roughness: .5, transparent: true }); mats.push(m);
    const lines = new THREE.Mesh(new THREE.PlaneGeometry(1.0, 1.4), m); lines.rotation.x = -Math.PI / 2; lines.position.set(side * .6, .185, 0); half.add(lines);
    half.rotation.z = side * .14; half.position.y = .12; g.add(half);
  });
  const spine = mesh(new THREE.CylinderGeometry(.09, .09, 1.7, 20), cover); spine.rotation.x = Math.PI / 2; spine.position.set(0, .06, 0); g.add(spine);
  const ribbon = mesh(new THREE.BoxGeometry(.12, .02, .9), std('#FFB45E')); ribbon.position.set(.16, .2, .95); ribbon.rotation.x = .35; g.add(ribbon);
  scene.add(g); return { g, mats };
}
function screenGlow(laptop) { // the laptop's screen material, made able to glow
  const mats = emissiveOf(laptop, (m) => !!m.map);
  mats.forEach((m) => { m.emissive = new THREE.Color('#7cc7ff'); m.emissiveMap = m.map; m.emissiveIntensity = 0; });
  return mats;
}
function lidOf(laptop) { let lid = null; laptop.traverse((o) => { if (!lid && o.isGroup && o !== laptop && Math.abs(o.rotation.x + .28) < .01) lid = o; }); return lid; }

Object.assign(SCENES, {
  // Hero: Tink keeps the record, ticking three items off the clipboard; each tick pops a check and blinks the bulb.
  hero() {
    const LOOP = 3.3, TICKS = [.35, 1.35, 2.35], TICK_D = .3;
    const tink = wrap(CAST.character('tink', 'happy')); const TINK = [0, 0, 0];
    let paper = null, bulb = null;
    tink.traverse((o) => {
      if (!o.isMesh) return;
      const p = o.geometry.parameters || {};
      if (o.geometry.type === 'PlaneGeometry' && Math.abs(p.width - .42) < .01) paper = o;
      if (o.geometry.type === 'SphereGeometry' && Math.abs(o.position.y - 2.1) < .01) bulb = o; // the antenna bulb
    });
    const cv = document.createElement('canvas'); cv.width = 128; cv.height = 152; const x = cv.getContext('2d');
    const tex = new THREE.CanvasTexture(cv); tex.encoding = THREE.sRGBEncoding; paper.material.map = tex; paper.material.needsUpdate = true;
    bulb.material = bulb.material.clone();
    function drawSheet(t) {
      const w = cv.width, h = cv.height, fade = 1 - P(t, 2.95, .3);
      x.fillStyle = '#FBF6EC'; x.fillRect(0, 0, w, h);
      x.lineCap = 'round'; x.lineJoin = 'round';
      for (let i = 0; i < 3; i++) {
        const y = h * (.22 + i * .28), u = clamp((t - TICKS[i]) / TICK_D);
        x.fillStyle = '#9fb2cc'; x.fillRect(w * .42, y - 6, w * .46, 10);
        if (u <= 0 || fade <= 0) continue;
        x.globalAlpha = fade; x.strokeStyle = '#2E9E5E'; x.lineWidth = 9;
        const a = [w * .1, y], b = [w * .2, y + 11], c = [w * .34, y - 13], k = clamp(u / .4), k2 = clamp((u - .4) / .6);
        x.beginPath(); x.moveTo(...a); x.lineTo(L(a[0], b[0], k), L(a[1], b[1], k)); if (k2 > 0) x.lineTo(L(b[0], c[0], k2), L(b[1], c[1], k2)); x.stroke();
        x.globalAlpha = 1;
      }
      tex.needsUpdate = true;
    }
    // a green check that pops off the clipboard and floats up
    const ck = document.createElement('canvas'); ck.width = 128; ck.height = 128; const cx = ck.getContext('2d');
    cx.fillStyle = '#2FBF71'; cx.beginPath(); cx.arc(64, 64, 58, 0, Math.PI * 2); cx.fill();
    cx.strokeStyle = '#FFFFFF'; cx.lineWidth = 14; cx.lineCap = 'round'; cx.lineJoin = 'round'; cx.beginPath(); cx.moveTo(36, 66); cx.lineTo(56, 86); cx.lineTo(92, 46); cx.stroke();
    const ckTex = new THREE.CanvasTexture(ck); ckTex.encoding = THREE.sRGBEncoding;
    const checks = TICKS.map(() => { const s = new THREE.Mesh(new THREE.PlaneGeometry(.3, .3), new THREE.MeshBasicMaterial({ map: ckTex, transparent: true, depthWrite: false, toneMapped: false })); scene.add(s); return s; });
    const sparks = TICKS.map(() => sparkSet(5, .045));
    aim([-.12, 1.15, 0], -10, 10, 7.2);
    return { LOOP, frame(t) {
      drawSheet(t);
      let sq = 0, lift = 0, glow = 0;
      TICKS.forEach((t0, i) => {
        const done = t0 + TICK_D, u = clamp((t - done) / .9);
        const on = t > done && u < 1;
        checks[i].visible = on;
        if (on) {
          checks[i].position.set(-.62 - .1 * i + u * .15, 1.42 + sm(u) * .75, .55);
          checks[i].scale.setScalar(back(clamp(u / .35)) * (1 - P(u, .7, .3)));
          checks[i].lookAt(camera.position);
        }
        burst(sparks[i], t, done, .5, V(-.56, 1.3, .5), .35);
        sq += bump(t, done - .05, .22); lift += bump(t, done, .4);
        glow = Math.max(glow, P(t, done, .06) * (1 - P(t, done + .15, .4)));
      });
      const sway = Math.sin(t / LOOP * Math.PI * 6) * .025;
      place(tink, [TINK[0], lift * .05, TINK[2]], 1, .32);
      tink.rotation.z = sway; tink.scale.y = 1 - sq * .05;
      bulb.material.emissiveIntensity = .6 + glow * 2.4;
      renderer.render(scene, camera);
    } };
  },

  // Team: one laptop's lesson goes up to the hub cloud, then down into two teammates' laptops; the transcript stays behind.
  team() {
    const LOOP = 3.6;
    const A = wrap(CAST.object('laptop')); place(A, [-2.55, 0, .35], .7, .5);
    const B = wrap(CAST.object('laptop')); place(B, [1.75, 0, .8], .62, -.42);
    const C = wrap(CAST.object('laptop')); place(C, [3.55, 0, -.25], .62, -.5);
    const scroll = wrap(CAST.object('log')); place(scroll, [-3.75, 0, -.35], .5, .45);
    const cloud = wrap(CAST.object('cloud')); const CLOUD = [.15, 1.35, -.9]; place(cloud, CLOUD, .66, 0);
    const cloudMats = emissiveOf(cloud, (m) => m.emissive && m.emissiveIntensity < .2);
    const scrA = screenGlow(A), scrB = screenGlow(B), scrC = screenGlow(C);
    const pA = wrap(CAST.character('pip', 'happy')), pB = wrap(CAST.character('pip', 'happy')), pC = wrap(CAST.character('pip', 'happy'));
    const sparks = sparkSet(7), sB = sparkSet(4, .05), sC = sparkSet(4, .05);
    const OUT_A = V(-2.4, .55, .3), CL_IN = V(.15, 2.1, -.6), CL_OUT = V(.25, 1.5, -.5), IN_B = V(1.7, .62, .6), IN_C = V(3.45, .62, -.4);
    aim([-.05, 1.15, 0], -4, 15, 12.9);
    function hopper(w, pos, s, ry, tilt) { place(w, [pos.x, pos.y, pos.z], .5 * s, ry); w.rotation.z = tilt; w.visible = s > .002; }
    return { LOOP, frame(t) {
      // up: out of laptop A, arc into the cloud
      if (t < .35) hopper(pA, OUT_A, back(t / .35), .4, 0);
      else if (t < 1.25) { const u = (t - .35) / .9; hopper(pA, qarc(OUT_A, CL_IN, .9, sm(u)), 1, .4, L(.2, -.3, u)); }
      else { const u = clamp((t - 1.25) / .25); hopper(pA, CL_IN.clone().add(V(0, -u * .3, 0)), 1 - sm(u), .4, -.3); }
      // the cloud takes it in
      const glow = P(t, 1.3, .25) * (1 - P(t, 2.1, .6));
      cloudMats.forEach((m) => { m.emissiveIntensity = .08 + glow * 1.0; });
      place(cloud, [CLOUD[0], CLOUD[1] + Math.sin(t / LOOP * Math.PI * 2) * .05 + bump(t, 1.3, .5) * .1, CLOUD[2]], .66, 0);
      cloud.scale.y *= 1 - bump(t, 1.28, .2) * .1 + bump(t, 1.48, .35) * .05;
      burst(sparks, t, 1.32, .65, V(CL_IN.x, CL_IN.y, CL_IN.z + .4), .7);
      // down: two copies out of the cloud, into laptops B and C
      [[pB, IN_B, 1.75, -.4], [pC, IN_C, 1.9, -.5]].forEach(([w, dst, t0, ry]) => {
        if (t < t0) { w.visible = false; return; }
        if (t < t0 + .25) { hopper(w, CL_OUT, back((t - t0) / .25), ry, 0); return; }
        const u = clamp((t - t0 - .25) / .75);
        if (u < 1) { hopper(w, qarc(CL_OUT, dst, .55, sm(u)), 1, ry, L(-.2, .25, u)); return; }
        const v = clamp((t - t0 - 1.0) / .22); hopper(w, dst.clone().add(V(0, -v * .1, 0)), 1 - sm(v), ry, .25);
      });
      burst(sB, t, 2.75, .45, V(IN_B.x, IN_B.y + .3, IN_B.z + .3), .4);
      burst(sC, t, 2.9, .45, V(IN_C.x, IN_C.y + .3, IN_C.z + .3), .4);
      scrA.forEach((m) => { m.emissiveIntensity = P(t, 0, .05) * (1 - P(t, .05, .45)) * .6; });
      scrB.forEach((m) => { m.emissiveIntensity = P(t, 2.75, .12) * (1 - P(t, 2.95, .5)) * .7; });
      scrC.forEach((m) => { m.emissiveIntensity = P(t, 2.9, .12) * (1 - P(t, 3.1, .45)) * .7; });
      renderer.render(scene, camera);
    } };
  },

  // Editor: Pip climbs out of the Knowledge book with a lesson and hops into the laptop, where a side panel lights up.
  editor() {
    const LOOP = 3.2;
    const laptop = wrap(CAST.object('laptop')); place(laptop, [-1.35, 0, -.1], .9, .42);
    const scr = screenGlow(laptop);
    const lid = lidOf(laptop);
    const panel = new THREE.Mesh(new THREE.PlaneGeometry(.52, .9), new THREE.MeshBasicMaterial({ color: '#6FE3C1', transparent: true, opacity: 0, depthWrite: false, toneMapped: false }));
    panel.position.set(.6, .66, .06); lid.add(panel);
    const book = makeBook(); book.g.position.set(1.55, 0, .25); book.g.rotation.y = -.25; book.g.scale.setScalar(.85);
    const pip = wrap(CAST.character('pip', 'happy'));
    const sparks = sparkSet(6, .055), sparks2 = sparkSet(5, .05);
    const OUT = V(1.3, .4, .3), HOP_END = V(.25, 0, .35), INTO = V(-1.0, .85, -.2);
    aim([.0, .95, 0], -6, 15, 8.0);
    return { LOOP, frame(t) {
      let pos, s = 1, sy = 1, tilt = 0;
      if (t < .4) { const u = t / .4; pos = OUT.clone(); pos.y += u * .25; s = back(u); }
      else if (t < 1.3) { const u = (t - .4) / .9, e = sm(u); pos = qarc(OUT.clone().add(V(0, .25, 0)), HOP_END, .5, e); const hp = (u * 2) % 1; pos.y += Math.sin(hp * Math.PI) * .18 * (u > .5 ? 1 : .4); sy = 1 + Math.sin(hp * Math.PI) * .06; tilt = .1; }
      else if (t < 1.9) { const u = (t - 1.3) / .6; pos = qarc(HOP_END, INTO, .9, sm(u)); sy = 1 + Math.sin(u * Math.PI) * .1; tilt = L(.15, -.2, u); }
      else { const u = clamp((t - 1.9) / .25); pos = INTO.clone(); s = 1 - sm(u); tilt = -.2; }
      place(pip, [pos.x, pos.y, pos.z], .62 * s, -.6);
      pip.scale.y *= sy; pip.rotation.z = tilt; pip.visible = s > .002;
      burst(sparks, t, .05, .55, V(OUT.x, OUT.y + .2, OUT.z + .2), .5);
      const bookGlow = P(t, 0, .1) * (1 - P(t, .25, .55));
      book.mats.forEach((m) => { m.emissiveIntensity = bookGlow * .85; });
      const lit = P(t, 1.95, .2) * (1 - P(t, 2.6, .5));
      panel.material.opacity = lit * .75;
      scr.forEach((m) => { m.emissiveIntensity = lit * .35; });
      burst(sparks2, t, 1.95, .55, V(INTO.x + .3, INTO.y + .2, INTO.z + .4), .5);
      renderer.render(scene, camera);
    } };
  },
});
