// v3 全局游戏状态（Zustand）
import { create } from 'zustand';
import {
  WorldMeta,
  EventRecord,
  Character,
  Group,
  Item,
  MapRecord,
  SaveInfo,
  TickResponse,
  TimeJumpResponse,
} from '../api/types';
import { savesApi, worldApi, agentApi, entitiesApi } from '../api/client';

export type TimeMode = 'auto' | 'manual' | 'paused';
export type AutoSpeed = '10s' | '1m' | '5m' | '30m' | '1h' | '4h' | '1d';

// 自动模式对应的真实间隔（毫秒）+ 游戏 tick 秒数
export const AUTO_SPEED_PRESETS: Record<AutoSpeed, { intervalMs: number; tickSeconds: number; label: string }> = {
  '10s': { intervalMs: 10_000, tickSeconds: 10, label: '10 秒' },
  '1m':  { intervalMs: 60_000, tickSeconds: 60, label: '1 分钟' },
  '5m':  { intervalMs: 300_000, tickSeconds: 300, label: '5 分钟' },
  '30m': { intervalMs: 1_800_000, tickSeconds: 1_800, label: '30 分钟' },
  '1h':  { intervalMs: 3_600_000, tickSeconds: 3_600, label: '1 小时' },
  '4h':  { intervalMs: 14_400_000, tickSeconds: 14_400, label: '4 小时' },
  '1d':  { intervalMs: 86_400_000, tickSeconds: 86_400, label: '1 天' },
};

// 时间跨越预设（游戏内秒数）
export const TIME_JUMP_PRESETS: Record<string, { seconds: number; label: string; confirm: string }> = {
  '3d':    { seconds: 86400 * 3,           label: '3 天',     confirm: '将跨越 3 天' },
  '7d':    { seconds: 86400 * 7,           label: '7 天',     confirm: '将跨越 7 天' },
  '30d':   { seconds: 86400 * 30,          label: '30 天',    confirm: '将跨越 30 天' },
  '100d':  { seconds: 86400 * 100,         label: '100 天',   confirm: '将跨越 100 天' },
  '1y':    { seconds: 86400 * 365,         label: '1 年',     confirm: '将跨越 1 年' },
  '3y':    { seconds: 86400 * 365 * 3,     label: '3 年',     confirm: '将跨越 3 年' },
  '10y':   { seconds: 86400 * 365 * 10,    label: '10 年',    confirm: '将跨越 10 年' },
  '100y':  { seconds: 86400 * 365 * 100,   label: '100 年',   confirm: '将跨越 100 年' },
  '1000y': { seconds: 86400 * 365 * 1000,  label: '1000 年',  confirm: '将跨越 1000 年' },
  '10000y':{ seconds: 86400 * 365 * 10000, label: '10000 年', confirm: '将跨越 10000 年' },
};

export type RightPanelTab = 'characters' | 'groups' | 'items' | 'maps' | 'memory';

interface GameState {
  // 存档
  saves: string[];
  activeSave: string | null;
  meta: WorldMeta | null;
  protagonist: Character | null;

  // 时间
  timeMode: TimeMode;
  autoSpeed: AutoSpeed;
  autoTimerId: number | null;
  lastTickResult: TickResponse | null;
  lastTimeJumpResult: TimeJumpResponse | null;
  isProcessing: boolean;

  // 事件流
  events: EventRecord[];
  eventsLoading: boolean;
  eventsFilter: {
    participantCharId: number | null;
    eventType: string;
    importanceMin: number;
    showRaw: boolean;
  };

  // 右面板
  rightTab: RightPanelTab;
  characters: Character[];
  groups: Group[];
  items: Item[];
  maps: MapRecord[];

  // 地图浏览器（菜单栏 → 🗺 地图 打开的全屏浮层）
  mapBrowserOpen: boolean;
  mapBrowserMapId: number | null;

  // 错误/通知
  error: string | null;
  notification: string | null;

  // Actions
  refreshSaves: () => Promise<void>;
  createSave: (name: string) => Promise<void>;
  switchSave: (name: string) => Promise<void>;
  deleteSave: (name: string) => Promise<void>;
  refreshMeta: () => Promise<void>;
  refreshEvents: () => Promise<void>;
  refreshCharacters: () => Promise<void>;
  refreshGroups: () => Promise<void>;
  refreshItems: () => Promise<void>;
  refreshMaps: () => Promise<void>;
  refreshAll: () => Promise<void>;

  setTimeMode: (mode: TimeMode) => void;
  setAutoSpeed: (speed: AutoSpeed) => void;
  startAutoTick: () => void;
  stopAutoTick: () => void;
  runTickOnce: (seconds: number) => Promise<void>;
  runTimeJump: (seconds: number) => Promise<void>;

  setRightTab: (tab: RightPanelTab) => void;
  setEventsFilter: (filter: Partial<GameState['eventsFilter']>) => void;
  openMapBrowser: (mapId?: number | null) => void;
  closeMapBrowser: () => void;
  setError: (msg: string | null) => void;
  setNotification: (msg: string | null) => void;
}

export const useGameStore = create<GameState>((set, get) => ({
  saves: [],
  activeSave: null,
  meta: null,
  protagonist: null,

  timeMode: 'paused',
  autoSpeed: '1m',
  autoTimerId: null,
  lastTickResult: null,
  lastTimeJumpResult: null,
  isProcessing: false,

  events: [],
  eventsLoading: false,
  eventsFilter: {
    participantCharId: null,
    eventType: '',
    importanceMin: 0,
    showRaw: false,
  },

  rightTab: 'characters',
  characters: [],
  groups: [],
  items: [],
  maps: [],

  mapBrowserOpen: false,
  mapBrowserMapId: null,

  error: null,
  notification: null,

  refreshSaves: async () => {
    try {
      const saves = await savesApi.list();
      set({ saves });
    } catch (e) {
      set({ error: `列出存档失败：${(e as Error).message}` });
    }
  },

  createSave: async (name) => {
    try {
      await savesApi.create(name);
      await get().refreshSaves();
      await get().switchSave(name);
      set({ notification: `存档「${name}」已创建并激活` });
    } catch (e) {
      set({ error: `创建存档失败：${(e as Error).message}` });
    }
  },

  switchSave: async (name) => {
    try {
      await savesApi.switch(name);
      set({ activeSave: name });
      await get().refreshAll();
      set({ timeMode: 'paused' });
      get().stopAutoTick();
    } catch (e) {
      set({ error: `切换存档失败：${(e as Error).message}` });
    }
  },

  deleteSave: async (name) => {
    try {
      await savesApi.delete(name);
      if (get().activeSave === name) {
        set({ activeSave: null, meta: null, events: [], characters: [] });
      }
      await get().refreshSaves();
      set({ notification: `存档「${name}」已删除` });
    } catch (e) {
      set({ error: `删除存档失败：${(e as Error).message}` });
    }
  },

  refreshMeta: async () => {
    try {
      const meta = await savesApi.getMeta();
      set({ meta });
      const prot = await savesApi.getProtagonist();
      set({ protagonist: prot?.protagonist ?? null });
    } catch {
      // 无激活存档
      set({ meta: null, protagonist: null });
    }
  },

  refreshEvents: async () => {
    set({ eventsLoading: true });
    try {
      const data = await worldApi.events({ limit: 100 });
      set({ events: data.items ?? [], eventsLoading: false });
    } catch (e) {
      set({ eventsLoading: false, error: `加载事件失败：${(e as Error).message}` });
    }
  },

  refreshCharacters: async () => {
    try {
      const chars = await entitiesApi.list<Character>('character', { limit: 200 });
      set({ characters: chars });
    } catch {
      set({ characters: [] });
    }
  },

  refreshGroups: async () => {
    try {
      const groups = await entitiesApi.list<Group>('group', { limit: 200 });
      set({ groups });
    } catch {
      set({ groups: [] });
    }
  },

  refreshItems: async () => {
    try {
      const items = await entitiesApi.list<Item>('item', { limit: 200 });
      set({ items });
    } catch {
      set({ items: [] });
    }
  },

  refreshMaps: async () => {
    try {
      const maps = await entitiesApi.list<MapRecord>('map', { limit: 100 });
      set({ maps });
    } catch {
      set({ maps: [] });
    }
  },

  refreshAll: async () => {
    await Promise.all([
      get().refreshMeta(),
      get().refreshEvents(),
      get().refreshCharacters(),
      get().refreshGroups(),
      get().refreshItems(),
      get().refreshMaps(),
    ]);
  },

  setTimeMode: (mode) => {
    set({ timeMode: mode });
    if (mode !== 'auto') {
      get().stopAutoTick();
    }
  },

  setAutoSpeed: (speed) => {
    set({ autoSpeed: speed });
    // 若当前在 auto 模式，重启计时器以应用新间隔
    if (get().timeMode === 'auto') {
      get().startAutoTick();
    }
  },

  startAutoTick: () => {
    get().stopAutoTick();
    const preset = AUTO_SPEED_PRESETS[get().autoSpeed];
    if (!preset) return;
    const timerId = window.setInterval(() => {
      get().runTickOnce(preset.tickSeconds);
    }, preset.intervalMs);
    set({ autoTimerId: timerId, timeMode: 'auto' });
  },

  stopAutoTick: () => {
    const tid = get().autoTimerId;
    if (tid !== null) {
      window.clearInterval(tid);
      set({ autoTimerId: null });
    }
  },

  runTickOnce: async (seconds) => {
    if (get().isProcessing) return;
    set({ isProcessing: true });
    try {
      const result = await agentApi.tick(seconds, 5);
      set({ lastTickResult: result });
      await get().refreshMeta();
      await get().refreshEvents();
      if (result.mock_mode) {
        set({ notification: `Tick ${result.tick} 完成（mock 模式）` });
      }
    } catch (e) {
      set({ error: `Tick 失败：${(e as Error).message}` });
    } finally {
      set({ isProcessing: false });
    }
  },

  runTimeJump: async (seconds) => {
    if (get().isProcessing) return;
    set({ isProcessing: true });
    try {
      const result = await agentApi.timeJump(seconds);
      set({ lastTimeJumpResult: result });
      await get().refreshMeta();
      await get().refreshEvents();
      await get().refreshCharacters();
      await get().refreshGroups();
      set({ notification: `时间跨越：${result.span_label}` });
    } catch (e) {
      set({ error: `时间跨越失败：${(e as Error).message}` });
    } finally {
      set({ isProcessing: false });
    }
  },

  setRightTab: (tab) => set({ rightTab: tab }),

  setEventsFilter: (filter) =>
    set((s) => ({ eventsFilter: { ...s.eventsFilter, ...filter } })),

  openMapBrowser: (mapId) =>
    set({ mapBrowserOpen: true, mapBrowserMapId: mapId ?? null }),
  closeMapBrowser: () => set({ mapBrowserOpen: false }),

  setError: (msg) => set({ error: msg }),
  setNotification: (msg) => set({ notification: msg }),
}));
