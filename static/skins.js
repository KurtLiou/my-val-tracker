/* 對戰陪伴的角色外觀（全部原創）。每個角色都有 4 種表情：happy / wow / sad / cheer */
"use strict";

(function () {
  const uid = () => "s" + Math.random().toString(36).slice(2, 8);

  /* ---------- 啾啾（原本的小機器人） ---------- */
  function jiujiu(mood) {
    const g = uid();
    const mouth = mood === "sad" ? '<path d="M42 66 q8 -6 16 0" stroke="#c7cdf5" stroke-width="3" fill="none" stroke-linecap="round"/>'
      : mood === "wow" ? '<ellipse cx="50" cy="64" rx="5" ry="6" fill="#c7cdf5"/>'
      : mood === "cheer" ? '<path d="M40 60 q10 12 20 0 z" fill="#c7cdf5"/>'
      : '<path d="M41 62 q9 9 18 0" stroke="#c7cdf5" stroke-width="3" fill="none" stroke-linecap="round"/>';
    const eyes = mood === "wow"
      ? '<path d="M33 50 l6 -5 l6 5" stroke="#4fe3b5" stroke-width="4" fill="none" stroke-linecap="round"/><path d="M55 50 l6 -5 l6 5" stroke="#4fe3b5" stroke-width="4" fill="none" stroke-linecap="round"/>'
      : mood === "cheer"
        ? '<path d="M33 50 q6 -6 12 0" stroke="#4fe3b5" stroke-width="4" fill="none" stroke-linecap="round"/><g class="eye"><ellipse cx="61" cy="50" rx="5" ry="6.5" fill="#4fe3b5"/><circle cx="63" cy="47.5" r="1.8" fill="#fff"/></g>'
        : '<g class="eye"><ellipse cx="39" cy="50" rx="5" ry="6.5" fill="#4fe3b5"/><circle cx="41" cy="47.5" r="1.8" fill="#fff"/></g><g class="eye"><ellipse cx="61" cy="50" rx="5" ry="6.5" fill="#4fe3b5"/><circle cx="63" cy="47.5" r="1.8" fill="#fff"/></g>';
    return `<svg viewBox="0 0 100 100"><defs><linearGradient id="${g}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#dfe3ff"/></linearGradient></defs>
      <line x1="50" y1="22" x2="50" y2="10" stroke="#c7cdf5" stroke-width="3" stroke-linecap="round"/>
      <path d="M50 2 l2.6 5.3 5.8.8 -4.2 4.1 1 5.8 -5.2-2.7 -5.2 2.7 1-5.8 -4.2-4.1 5.8-.8z" fill="#ffd166"/>
      <ellipse cx="14" cy="56" rx="7" ry="11" fill="#ff4f64"/><ellipse cx="86" cy="56" rx="7" ry="11" fill="#ff4f64"/>
      <rect x="16" y="20" width="68" height="66" rx="32" fill="url(#${g})"/><rect x="25" y="34" width="50" height="38" rx="18" fill="#2a2f55"/>
      ${eyes}<g transform="translate(0,-2)">${mouth}</g>
      <ellipse cx="30" cy="62" rx="4" ry="2.5" fill="#ff9f80" opacity="${mood === "sad" ? ".3" : ".85"}"/><ellipse cx="70" cy="62" rx="4" ry="2.5" fill="#ff9f80" opacity="${mood === "sad" ? ".3" : ".85"}"/>
      ${mood === "sad" ? '<path d="M66 58 q2 6 0 8 q-2 -2 0 -8z" fill="#7fc7ff"/>' : ""}
      <path d="M38 86 q12 8 24 0" fill="#c7cdf5"/></svg>`;
  }

  /* ---------- 原創動漫風女孩（參數化） ---------- */
  function eye(cx, cy, c, mood, side) {
    const g = uid();
    if (mood === "cheer" && side === "L") {
      return `<path d="M${cx - 6} ${cy + 1} q6 -7 12 0" stroke="${c.line}" stroke-width="2.4" fill="none" stroke-linecap="round"/>`;
    }
    const lid = mood === "sad"
      ? `<path d="M${cx - 7} ${cy - 8} L${cx + 7} ${cy - 8} L${cx + 7} ${cy - 2} Q${cx} ${cy - 5} ${cx - 7} ${cy - 1}z" fill="${c.skin}"/>` : "";
    const star = mood === "wow"
      ? `<path d="M${cx} ${cy - 4} l1.3 2.7 3 .4 -2.2 2.1 .5 3 -2.6-1.4 -2.6 1.4 .5-3 -2.2-2.1 3-.4z" fill="#fff"/>`
      : `<ellipse cx="${cx}" cy="${cy + 1}" rx="2.4" ry="3.2" fill="${c.pupil}"/>
         <circle cx="${cx + 1.8}" cy="${cy - 2.4}" r="1.9" fill="#fff"/><circle cx="${cx - 1.8}" cy="${cy + 3}" r=".9" fill="#fff"/>`;
    return `<g class="eye"><defs><linearGradient id="${g}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${c.eyeTop}"/><stop offset="1" stop-color="${c.eye}"/></linearGradient></defs>
      <ellipse cx="${cx}" cy="${cy}" rx="6" ry="7.5" fill="#fff"/>
      <ellipse cx="${cx}" cy="${cy + .5}" rx="5" ry="6.6" fill="url(#${g})"/>${star}${lid}
      <path d="M${cx - 7} ${cy - 5} Q${cx} ${cy - 10} ${cx + 7} ${cy - 5}" stroke="${c.line}" stroke-width="2.2" fill="none" stroke-linecap="round"/></g>`;
  }
  function mouthOf(mood, c) {
    if (mood === "wow") return `<ellipse cx="50" cy="69" rx="3.2" ry="3.8" fill="#c44a5a"/><ellipse cx="50" cy="70.5" rx="2" ry="1.4" fill="#ff8fa0"/>`;
    if (mood === "sad") return `<path d="M46 70 q4 -3 8 0" stroke="${c.line}" stroke-width="1.8" fill="none" stroke-linecap="round"/>`;
    if (mood === "cheer") return `<path d="M44.5 66.5 q5.5 8 11 0 z" fill="#c44a5a"/><path d="M46.5 69 q3.5 2.5 7 0" fill="#ff8fa0"/>`;
    return `<path d="M46 67 q4 4 8 0" stroke="${c.line}" stroke-width="1.8" fill="none" stroke-linecap="round"/>`;
  }
  function girl(c) {
    return function (mood) {
      const brow = mood === "sad"
        ? `<path d="M33 47.5 q4.5 -1 9 -4" stroke="${c.hairDark}" stroke-width="1.6" fill="none" stroke-linecap="round"/><path d="M67 47.5 q-4.5 -1 -9 -4" stroke="${c.hairDark}" stroke-width="1.6" fill="none" stroke-linecap="round"/>`
        : `<path d="M33 46 q5 -2.5 9 -.5" stroke="${c.hairDark}" stroke-width="1.5" fill="none" stroke-linecap="round"/><path d="M67 46 q-5 -2.5 -9 -.5" stroke="${c.hairDark}" stroke-width="1.5" fill="none" stroke-linecap="round"/>`;
      return `<svg viewBox="0 0 100 100">
        ${c.back}
        <path d="M28 100 Q30 80 50 79 Q70 80 72 100z" fill="${c.outfit}"/>
        <path d="M43 79 L50 87 L57 79" fill="${c.collar}"/>
        <rect x="45" y="72" width="10" height="9" rx="3" fill="${c.skinShade}"/>
        <ellipse cx="50" cy="54" rx="25" ry="24" fill="${c.skin}"/>
        ${c.side}
        <path d="M24 54 Q20 22 50 20 Q80 22 76 54 Q73 40 66 38 Q63 44 57 41 Q53 33 50 41 Q45 33 41 41 Q35 44 33 38 Q27 41 24 54z" fill="${c.hair}"/>
        <path d="M50 20 Q62 21 70 30" stroke="${c.hairShine}" stroke-width="2.5" fill="none" stroke-linecap="round" opacity=".7"/>
        ${brow}
        ${eye(39, 56, c, mood, "L")}${eye(61, 56, c, mood, "R")}
        <ellipse cx="32" cy="65" rx="4.5" ry="2.4" fill="#ff8fa8" opacity="${mood === "sad" ? ".25" : ".6"}"/>
        <ellipse cx="68" cy="65" rx="4.5" ry="2.4" fill="#ff8fa8" opacity="${mood === "sad" ? ".25" : ".6"}"/>
        ${mouthOf(mood, c)}
        ${mood === "sad" ? `<path d="M67 61 q2.5 6 0 8.5 q-2.5 -2.5 0 -8.5z" fill="#8fd0ff"/>` : ""}
        ${c.front}
      </svg>`;
    };
  }

  const base = { skin: "#ffe6d8", skinShade: "#f6cbb7", line: "#4a2f3a", pupil: "#2a1830" };

  const hoshina = girl({ ...base, // 星奈：粉色雙馬尾、星星髮夾
    hair: "#ff8fb8", hairDark: "#d9628f", hairShine: "#ffd1e3", eye: "#e0457a", eyeTop: "#ff9ec0",
    outfit: "#3b3f7a", collar: "#ffffff",
    back: `<path d="M24 46 Q6 58 10 92 Q18 76 22 62z" fill="#ff8fb8"/><path d="M76 46 Q94 58 90 92 Q82 76 78 62z" fill="#ff8fb8"/>
           <circle cx="25" cy="42" r="4" fill="#5ad1ff"/><circle cx="75" cy="42" r="4" fill="#5ad1ff"/>`,
    side: `<path d="M26 50 Q24 66 28 74 Q30 62 30 52z" fill="#ff8fb8"/><path d="M74 50 Q76 66 72 74 Q70 62 70 52z" fill="#ff8fb8"/>`,
    front: `<path d="M68 28 l2.2 4.5 5 .7 -3.6 3.5 .9 5 -4.5-2.4 -4.5 2.4 .9-5 -3.6-3.5 5-.7z" fill="#ffd166" stroke="#e0a800" stroke-width=".8"/>`,
  });
  const rinne = girl({ ...base, // 凜音：銀色短髮、貓耳帽 T
    hair: "#dfe3f5", hairDark: "#8f96b8", hairShine: "#ffffff", eye: "#5a6dff", eyeTop: "#9fb0ff",
    outfit: "#2b2f45", collar: "#a98bff",
    back: `<path d="M22 34 L28 12 L40 26z" fill="#2b2f45"/><path d="M26 30 L29 18 L35 26z" fill="#ff9ec0"/>
           <path d="M78 34 L72 12 L60 26z" fill="#2b2f45"/><path d="M74 30 L71 18 L65 26z" fill="#ff9ec0"/>
           <path d="M22 50 Q18 22 50 16 Q82 22 78 50 Q76 30 50 26 Q24 30 22 50z" fill="#2b2f45"/>`,
    side: `<path d="M25 52 Q24 64 30 70 Q29 60 30 52z" fill="#dfe3f5"/><path d="M75 52 Q76 64 70 70 Q71 60 70 52z" fill="#dfe3f5"/>`,
    front: `<circle cx="36" cy="88" r="2" fill="#a98bff"/><circle cx="64" cy="88" r="2" fill="#a98bff"/>`,
  });
  const wakaba = girl({ ...base, // 若葉：綠色長髮、大蝴蝶結
    hair: "#5fcf9a", hairDark: "#2f9a6b", hairShine: "#c8ffe4", eye: "#e08a2a", eyeTop: "#ffd07a",
    outfit: "#fff4e0", collar: "#ff6b81",
    back: `<path d="M24 40 Q8 70 18 100 L82 100 Q92 70 76 40 Q70 70 50 74 Q30 70 24 40z" fill="#5fcf9a"/>`,
    side: `<path d="M26 50 Q22 70 26 84 Q31 68 31 52z" fill="#5fcf9a"/><path d="M74 50 Q78 70 74 84 Q69 68 69 52z" fill="#5fcf9a"/>`,
    front: `<path d="M50 22 L36 14 Q32 22 36 30z" fill="#ff6b81"/><path d="M50 22 L64 14 Q68 22 64 30z" fill="#ff6b81"/>
            <circle cx="50" cy="22" r="3.5" fill="#ff4f64"/>`,
  });

  window.SKINS = {
    jiujiu: { name: "啾啾", desc: "漂浮小機器人", svg: jiujiu },
    hoshina: { name: "星奈", desc: "粉色雙馬尾的元氣少女", svg: hoshina },
    rinne: { name: "凜音", desc: "戴貓耳帽的酷酷少女", svg: rinne },
    wakaba: { name: "若葉", desc: "綠髮大蝴蝶結的溫柔少女", svg: wakaba },
    custom: { name: "自訂圖片", desc: "用你自己的圖片", svg: null },
  };
})();
