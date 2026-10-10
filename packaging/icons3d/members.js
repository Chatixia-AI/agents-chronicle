// Interlatch-only members, built from CAST.parts so they share the cast's materials.
window.CUSTOM = {
  // Knowledge: an open book on its spine, pages printed with transcript-like lines, amber ribbon.
  book(CAST, scene) {
    const { glossy, std, mesh, roundBox, texPlane } = CAST.parts;
    const g = new THREE.Group();
    const cover = glossy('#4FC9A8'), paper = std('#FBF6EC', { roughness: .6 });
    [-1, 1].forEach((side) => {
      const half = new THREE.Group();
      const c = mesh(roundBox(1.25, 1.7, .08, .08, .03), cover);
      c.rotation.x = -Math.PI / 2; c.position.set(side * .64, 0, .85);
      half.add(c);
      const pages = mesh(roundBox(1.12, 1.56, .16, .03, .02), paper);
      pages.rotation.x = -Math.PI / 2; pages.position.set(side * .6, .1, .78);
      half.add(pages);
      const lines = texPlane(1.0, 1.4, (x, w, h) => {
        x.clearRect(0, 0, w, h);
        const cols = side < 0 ? ['#2F7FD0', '#5D86B6', '#5D86B6', '#E8902A', '#5D86B6', '#5D86B6', '#22A884']
          : ['#7458E0', '#5D86B6', '#5D86B6', '#5D86B6', '#2F7FD0', '#5D86B6', '#5D86B6'];
        cols.forEach((col, i) => {
          x.fillStyle = col;
          const wd = i === 0 ? .5 : [.82, .74, .86, .6, .78, .7][(i + (side > 0 ? 2 : 0)) % 6];
          x.beginPath(); x.roundRect(w * .06, h * (.08 + i * .125), w * wd, h * (i === 0 ? .06 : .04), h * .02); x.fill();
        });
      }, 256);
      lines.rotation.x = -Math.PI / 2; lines.position.set(side * .6, .185, 0);
      half.add(lines);
      half.rotation.z = side * .14; // a shallow V: pages rise away from the spine
      half.position.y = .12;
      g.add(half);
    });
    const spine = mesh(new THREE.CylinderGeometry(.09, .09, 1.7, 20), cover);
    spine.rotation.x = Math.PI / 2; spine.position.set(0, .06, 0); g.add(spine);
    const ribbon = mesh(new THREE.BoxGeometry(.12, .02, .9), std('#FFB45E'));
    ribbon.position.set(.16, .2, .95); ribbon.rotation.x = .35; g.add(ribbon);
    scene.add(g); return g;
  },

  // Interlatch's emblem in 3D: two sky-blue sheets behind an amber sheet with a folded corner and two transcript strokes.
  stack(CAST, scene) {
    const { glossy, std, mesh, roundBox, extrudeShape } = CAST.parts;
    const g = new THREE.Group();
    const sheet = (w, h, fold) => {
      const s = new THREE.Shape(), r = .1;
      s.moveTo(-w / 2 + r, 0); s.lineTo(w / 2 - r, 0); s.quadraticCurveTo(w / 2, 0, w / 2, r);
      s.lineTo(w / 2, h - fold); s.lineTo(w / 2 - fold, h); s.lineTo(-w / 2 + r, h);
      s.quadraticCurveTo(-w / 2, h, -w / 2, h - r); s.lineTo(-w / 2, r); s.quadraticCurveTo(-w / 2, 0, -w / 2 + r, 0);
      return s;
    };
    const foldTri = (w, h, fold) => {
      const t = new THREE.Shape();
      t.moveTo(w / 2 - fold, h); t.lineTo(w / 2 - fold, h - fold + .06); t.quadraticCurveTo(w / 2 - fold, h - fold, w / 2 - fold + .06, h - fold); t.lineTo(w / 2, h - fold); t.closePath();
      return t;
    };
    const W = 1.5, H = 1.95, F = .5;
    [['#3E94E6', .7, -.56], ['#5DB2F5', .35, -.28]].forEach(([col, dx, dz]) => {
      const b = extrudeShape(sheet(W, H, F), .1, glossy(col), .04);
      b.position.set(dx, .12 + dx * .3, dz); g.add(b);
      const f = extrudeShape(foldTri(W, H, F), .03, glossy(new THREE.Color(col).multiplyScalar(.82)), .015);
      f.position.set(dx, .12 + dx * .3, dz + .08); g.add(f);
    });
    const front = extrudeShape(sheet(W, H, F), .12, glossy('#FFA02E'), .045);
    front.position.set(0, .12, 0); g.add(front);
    const fold = extrudeShape(foldTri(W, H, F), .04, glossy('#E07818'), .02);
    fold.position.set(0, .12, .1); g.add(fold);
    const navy = std('#0d2340', { roughness: .5 });
    [[.92, .98], [.66, .62]].forEach(([len, y]) => {
      const bar = mesh(roundBox(len, .16, .04, .08, .015), navy);
      bar.position.set(-W / 2 + .22 + len / 2, y + .12, .1); g.add(bar);
    });
    g.rotation.y = .12;
    scene.add(g); return g;
  },
};
