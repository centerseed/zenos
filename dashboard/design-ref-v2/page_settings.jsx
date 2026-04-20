// ZenOS v2 · Settings (個人設定)
const { useState: useSetS } = React;

function InkSettingsPage({ t }) {
  const { c, fontHead, fontMono, fontBody } = t;
  const [section, setSection] = useSetS("profile");

  const sections = [
    { k: "profile",    zh: "個人資料", en: "Profile" },
    { k: "rhythm",     zh: "工作節律", en: "Rhythm" },
    { k: "appearance", zh: "外觀",     en: "Appearance" },
    { k: "notifs",     zh: "通知",     en: "Notifications" },
    { k: "privacy",    zh: "隱私",     en: "Privacy" },
    { k: "account",    zh: "帳號",     en: "Account" },
  ];

  return (
    <div style={{ padding: "40px 48px 60px", maxWidth: 1600 }}>
      <Section t={t} eyebrow="SETTINGS · 設定" title="個人設定" en="Settings"
        subtitle="你的工作節律、外觀、通知偏好。團隊與 Agent 設定另有其頁。"
        right={<div style={{ display: "flex", gap: 10 }}>
          <Btn t={t} variant="ghost" size="sm">取消</Btn>
          <Btn t={t} variant="ink" size="sm" icon={Icons.check}>儲存</Btn>
        </div>}
      />

      <div style={{ display: "grid", gridTemplateColumns: "220px 1fr", gap: 32 }}>
        {/* Side nav */}
        <aside style={{ borderRight: `1px solid ${c.inkHair}`, paddingRight: 20 }}>
          <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.22em", textTransform: "uppercase", padding: "0 8px 10px" }}>
            Sections · 章節
          </div>
          {sections.map(s => (
            <button key={s.k} onClick={() => setSection(s.k)} style={{
              display: "grid", gridTemplateColumns: "1fr auto", alignItems: "center", gap: 8,
              padding: "9px 10px", width: "100%",
              background: section === s.k ? c.surface : "transparent",
              border: "none",
              borderLeft: section === s.k ? `2px solid ${c.vermillion}` : "2px solid transparent",
              color: section === s.k ? c.ink : c.inkMuted,
              cursor: "pointer", textAlign: "left", fontFamily: fontBody,
            }}>
              <span style={{ fontSize: 13, fontWeight: section === s.k ? 500 : 400, letterSpacing: "0.04em" }}>{s.zh}</span>
              <span style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.08em" }}>{s.en}</span>
            </button>
          ))}

          <div style={{
            marginTop: 28, padding: 14, background: c.paperWarm,
            border: `1px solid ${c.inkHair}`, borderRadius: 2,
          }}>
            <div style={{ fontFamily: fontMono, fontSize: 9, color: c.inkFaint, letterSpacing: "0.2em", marginBottom: 6 }}>節氣 · 穀雨</div>
            <div style={{ fontFamily: fontHead, fontSize: 13, color: c.ink, letterSpacing: "0.06em", lineHeight: 1.7 }}>
              雨生百穀，<br />萬物萌發。
            </div>
          </div>
        </aside>

        <div>
          {section === "profile"    && <ProfileSection t={t} />}
          {section === "rhythm"     && <RhythmSection t={t} />}
          {section === "appearance" && <AppearanceSection t={t} />}
          {section === "notifs"     && <NotifsSection t={t} />}
          {section === "privacy"    && <PrivacySection t={t} />}
          {section === "account"    && <AccountSection t={t} />}
        </div>
      </div>
    </div>
  );
}

// ─── shared setting-row primitives ─────────────────────────────────────
function SetGroup({ t, title, en, desc, children }) {
  const { c, fontHead, fontMono } = t;
  return (
    <div style={{ background: c.surface, border: `1px solid ${c.inkHair}`, borderRadius: 2, marginBottom: 20 }}>
      <div style={{ padding: "16px 22px", borderBottom: `1px solid ${c.inkHair}` }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
          <div style={{ fontFamily: fontHead, fontSize: 16, fontWeight: 500, color: c.ink, letterSpacing: "0.04em" }}>{title}</div>
          {en && <div style={{ fontFamily: fontMono, fontSize: 10, color: c.inkFaint, letterSpacing: "0.18em", textTransform: "uppercase" }}>{en}</div>}
        </div>
        {desc && <div style={{ fontSize: 12, color: c.inkMuted, marginTop: 4, lineHeight: 1.6 }}>{desc}</div>}
      </div>
      <div>{children}</div>
    </div>
  );
}
function SetRow({ t, label, hint, children, last }) {
  const { c } = t;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "240px 1fr", gap: 20,
      padding: "14px 22px", alignItems: "center",
      borderBottom: last ? "none" : `1px solid ${c.inkHair}`,
    }}>
      <div>
        <div style={{ fontSize: 13, color: c.ink, fontWeight: 500 }}>{label}</div>
        {hint && <div style={{ fontSize: 11, color: c.inkMuted, marginTop: 3, lineHeight: 1.5 }}>{hint}</div>}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>{children}</div>
    </div>
  );
}
function Toggle({ t, on, onChange }) {
  const { c } = t;
  return (
    <button onClick={() => onChange(!on)} style={{
      width: 36, height: 20, background: on ? c.vermillion : c.inkHair,
      border: "none", borderRadius: 10, cursor: "pointer", position: "relative",
      transition: "all .18s",
    }}>
      <span style={{
        position: "absolute", top: 2, left: on ? 18 : 2,
        width: 16, height: 16, background: c.paper, borderRadius: "50%",
        transition: "all .18s",
      }} />
    </button>
  );
}
function TextField({ t, value, placeholder, mono, wide, onChange }) {
  const { c, fontMono, fontBody } = t;
  return (
    <input value={value || ""} placeholder={placeholder} onChange={e => onChange?.(e.target.value)}
      style={{
        width: wide ? 320 : 200, padding: "6px 10px",
        background: c.paper, border: `1px solid ${c.inkHair}`, borderRadius: 2,
        color: c.ink, fontSize: 13, fontFamily: mono ? fontMono : fontBody,
        letterSpacing: "0.02em", outline: "none",
      }} />
  );
}
function SegCtl({ t, options, value, onChange }) {
  const { c, fontBody } = t;
  return (
    <div style={{ display: "flex", background: c.paperWarm, border: `1px solid ${c.inkHair}`, borderRadius: 2, padding: 2 }}>
      {options.map(([v, l]) => (
        <button key={v} onClick={() => onChange?.(v)} style={{
          padding: "5px 12px", background: value === v ? c.ink : "transparent",
          color: value === v ? c.paper : c.inkMuted, border: "none",
          borderRadius: 2, cursor: "pointer", fontSize: 12, fontFamily: fontBody, letterSpacing: "0.04em",
        }}>{l}</button>
      ))}
    </div>
  );
}

// ─── sections ──────────────────────────────────────────────────────────
function ProfileSection({ t }) {
  const { c, fontHead } = t;
  const [vals, setVals] = useSetS({
    name: "Barry Lin", handle: "@barry", title: "產品設計師", email: "barry@zenos.tw", lang: "zh-TW",
  });
  const up = (k, v) => setVals({ ...vals, [k]: v });

  return (
    <>
      <SetGroup t={t} title="身分" en="Identity" desc="顯示於晨報、共筆、任務等所有介面。">
        <SetRow t={t} label="頭像">
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{
              width: 56, height: 56, borderRadius: "50%",
              background: c.vermSoft, border: `1px solid ${c.vermLine}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontFamily: fontHead, fontSize: 22, fontWeight: 600, color: c.vermillion,
            }}>B</div>
            <Btn t={t} variant="outline" size="sm">更換</Btn>
            <Btn t={t} variant="ghost" size="sm">移除</Btn>
          </div>
        </SetRow>
        <SetRow t={t} label="姓名" hint="會在團隊成員、責任人等欄位中出現。">
          <TextField t={t} value={vals.name} onChange={v => up("name", v)} />
        </SetRow>
        <SetRow t={t} label="識別碼" hint="獨一無二，用於 @ 提及。">
          <TextField t={t} value={vals.handle} mono onChange={v => up("handle", v)} />
        </SetRow>
        <SetRow t={t} label="職稱">
          <TextField t={t} value={vals.title} onChange={v => up("title", v)} />
        </SetRow>
        <SetRow t={t} label="Email" last>
          <TextField t={t} value={vals.email} mono wide onChange={v => up("email", v)} />
        </SetRow>
      </SetGroup>

      <SetGroup t={t} title="語系與時區" en="Locale">
        <SetRow t={t} label="介面語言">
          <SegCtl t={t} options={[["zh-TW","繁中"],["zh-CN","简中"],["en","EN"],["ja","日"]]} value={vals.lang} onChange={v => up("lang", v)} />
        </SetRow>
        <SetRow t={t} label="時區">
          <TextField t={t} value="Asia/Taipei (GMT+8)" mono wide />
        </SetRow>
        <SetRow t={t} label="週起始" last>
          <SegCtl t={t} options={[["sun","日"],["mon","一"]]} value="mon" />
        </SetRow>
      </SetGroup>
    </>
  );
}

function RhythmSection({ t }) {
  const [vals, setVals] = useSetS({
    startHour: "09:00", endHour: "18:00", briefAt: "07:00", debriefAt: "17:30",
    deepBlocks: true, pomodoro: 50, breakAfter: true,
  });
  const up = (k, v) => setVals({ ...vals, [k]: v });
  return (
    <>
      <SetGroup t={t} title="一日之節" en="Daily Rhythm"
        desc="ZenOS 會在這些時刻整理晨報、提醒你進入深工時段、收工回看。">
        <SetRow t={t} label="開工時間">
          <TextField t={t} value={vals.startHour} mono onChange={v => up("startHour", v)} />
        </SetRow>
        <SetRow t={t} label="晨報產生時間" hint="Agent 於此時備妥當日焦點、新訊、會議。">
          <TextField t={t} value={vals.briefAt} mono onChange={v => up("briefAt", v)} />
        </SetRow>
        <SetRow t={t} label="收工盤點時間" hint="Agent 整理今日所成、明日所待。">
          <TextField t={t} value={vals.debriefAt} mono onChange={v => up("debriefAt", v)} />
        </SetRow>
        <SetRow t={t} label="下班時間" last>
          <TextField t={t} value={vals.endHour} mono onChange={v => up("endHour", v)} />
        </SetRow>
      </SetGroup>

      <SetGroup t={t} title="深工時段" en="Deep Work">
        <SetRow t={t} label="自動排入深工" hint="ZenOS 會於行事曆中預留 2×90 分鐘的深工時段。">
          <Toggle t={t} on={vals.deepBlocks} onChange={v => up("deepBlocks", v)} />
        </SetRow>
        <SetRow t={t} label="專注長度（分鐘）">
          <SegCtl t={t} options={[[25,"25"],[50,"50"],[90,"90"]]} value={vals.pomodoro} onChange={v => up("pomodoro", v)} />
        </SetRow>
        <SetRow t={t} label="結束後提醒休息" last>
          <Toggle t={t} on={vals.breakAfter} onChange={v => up("breakAfter", v)} />
        </SetRow>
      </SetGroup>
    </>
  );
}

function AppearanceSection({ t }) {
  const [vals, setVals] = useSetS({ mode: "light", density: "comfortable", font: 14, seasonal: true, grain: true });
  const up = (k, v) => setVals({ ...vals, [k]: v });
  return (
    <>
      <SetGroup t={t} title="風格" en="Appearance" desc="Zen Ink 是 ZenOS 的設計語言。你可以調整密度與字級。">
        <SetRow t={t} label="明暗">
          <SegCtl t={t} options={[["light","晝"],["dark","夜"],["auto","依系統"]]} value={vals.mode} onChange={v => up("mode", v)} />
        </SetRow>
        <SetRow t={t} label="密度">
          <SegCtl t={t} options={[["cozy","寬鬆"],["comfortable","舒適"],["compact","緊湊"]]} value={vals.density} onChange={v => up("density", v)} />
        </SetRow>
        <SetRow t={t} label="基礎字級">
          <SegCtl t={t} options={[[13,"S"],[14,"M"],[15,"L"],[16,"XL"]]} value={vals.font} onChange={v => up("font", v)} />
        </SetRow>
        <SetRow t={t} label="節氣水印" hint="於各頁角落顯示當下節氣書法字。">
          <Toggle t={t} on={vals.seasonal} onChange={v => up("seasonal", v)} />
        </SetRow>
        <SetRow t={t} label="紙紋質感" last>
          <Toggle t={t} on={vals.grain} onChange={v => up("grain", v)} />
        </SetRow>
      </SetGroup>
    </>
  );
}

function NotifsSection({ t }) {
  const [vals, setVals] = useSetS({
    brief: true, mention: true, assign: true, deadline: true, agent: false,
    email: true, push: true, dnd: true, dndFrom: "22:00", dndTo: "07:00",
  });
  const up = (k, v) => setVals({ ...vals, [k]: v });
  return (
    <>
      <SetGroup t={t} title="通知類型" en="Types">
        <SetRow t={t} label="晨報就緒"                    ><Toggle t={t} on={vals.brief}    onChange={v => up("brief", v)} /></SetRow>
        <SetRow t={t} label="被提及 · @"                   ><Toggle t={t} on={vals.mention}  onChange={v => up("mention", v)} /></SetRow>
        <SetRow t={t} label="新任務指派給我"               ><Toggle t={t} on={vals.assign}   onChange={v => up("assign", v)} /></SetRow>
        <SetRow t={t} label="任務到期提醒"                 ><Toggle t={t} on={vals.deadline} onChange={v => up("deadline", v)} /></SetRow>
        <SetRow t={t} label="Agent 建議" hint="Agent 想主動提議時才通知。" last>
          <Toggle t={t} on={vals.agent} onChange={v => up("agent", v)} />
        </SetRow>
      </SetGroup>

      <SetGroup t={t} title="通知管道" en="Channels">
        <SetRow t={t} label="Email"><Toggle t={t} on={vals.email} onChange={v => up("email", v)} /></SetRow>
        <SetRow t={t} label="瀏覽器 · Push" last><Toggle t={t} on={vals.push} onChange={v => up("push", v)} /></SetRow>
      </SetGroup>

      <SetGroup t={t} title="勿擾時段" en="Do Not Disturb">
        <SetRow t={t} label="啟用勿擾"><Toggle t={t} on={vals.dnd} onChange={v => up("dnd", v)} /></SetRow>
        <SetRow t={t} label="開始"><TextField t={t} value={vals.dndFrom} mono /></SetRow>
        <SetRow t={t} label="結束" last><TextField t={t} value={vals.dndTo} mono /></SetRow>
      </SetGroup>
    </>
  );
}

function PrivacySection({ t }) {
  const { c, fontMono } = t;
  return (
    <>
      <SetGroup t={t} title="資料授權" en="Data">
        <SetRow t={t} label="用於模型訓練" hint="關閉即代表：你的內容不會被用於訓練任何模型。">
          <Toggle t={t} on={false} onChange={() => {}} />
        </SetRow>
        <SetRow t={t} label="匿名使用數據" hint="協助改進產品體驗，所有資料皆去識別化。" last>
          <Toggle t={t} on={true} onChange={() => {}} />
        </SetRow>
      </SetGroup>
      <SetGroup t={t} title="資料管理" en="My Data">
        <SetRow t={t} label="匯出所有資料" hint="將你的知識地圖、任務、文件打包為 zip（Markdown + JSON）。">
          <Btn t={t} variant="outline" size="sm">匯出 · Export</Btn>
        </SetRow>
        <SetRow t={t} label="清除本機快取"><Btn t={t} variant="ghost" size="sm">清除</Btn></SetRow>
        <SetRow t={t} label="刪除帳號" hint="刪除後 30 天內可恢復；之後永久清除。" last>
          <Btn t={t} variant="outline" size="sm" style={{ color: c.seal, borderColor: c.vermLine }}>刪除…</Btn>
        </SetRow>
      </SetGroup>
    </>
  );
}

function AccountSection({ t }) {
  const { c } = t;
  return (
    <>
      <SetGroup t={t} title="訂閱" en="Subscription">
        <SetRow t={t} label="目前方案">
          <Chip t={t} tone="accent" dot>小隊 · Team</Chip>
        </SetRow>
        <SetRow t={t} label="下次計費日"><span style={{ color: c.ink, fontSize: 13 }}>2026 / 05 / 15</span></SetRow>
        <SetRow t={t} label="方案操作" last>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn t={t} variant="outline" size="sm">變更方案</Btn>
            <Btn t={t} variant="ghost" size="sm">查看發票</Btn>
          </div>
        </SetRow>
      </SetGroup>
      <SetGroup t={t} title="安全" en="Security">
        <SetRow t={t} label="雙重驗證" hint="以 App 驗證碼或硬體金鑰保護帳號。">
          <Btn t={t} variant="outline" size="sm">啟用</Btn>
        </SetRow>
        <SetRow t={t} label="登入過的裝置" last>
          <Btn t={t} variant="ghost" size="sm">檢視 · 4 台</Btn>
        </SetRow>
      </SetGroup>
    </>
  );
}

window.InkSettingsPage = InkSettingsPage;
