<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, COMBINE_STATUS } from '../lib/api.js';

  let houses = [];
  let vats = [];
  let rows = [];
  let error = '';
  let form = {
    dyeHouseId: '',
    batchCode: '',
    fabricLimitKg: 100,
    vatIds: [],
  };
  let editing = null;
  // 每行成员编辑态：{ [batchId]: number[] }
  let memberDraft = {};

  async function load() {
    error = '';
    try {
      [houses, vats, rows] = await Promise.all([
        api('/dye-houses'),
        api('/vats'),
        api('/combine-batches'),
      ]);
      if (!form.dyeHouseId && houses.length) form.dyeHouseId = String(houses[0].id);
      // 初始化每行成员草稿
      const draft = {};
      for (const b of rows) draft[b.id] = b.members.map((m) => m.vatId);
      memberDraft = draft;
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  $: houseId = Number(form.dyeHouseId);
  // 新建表单可选缸：所选染坊的就绪缸
  $: selectableVats = vats.filter((v) => v.dyeHouseId === houseId && v.status === 'ready');

  function houseName(id) {
    return houses.find((h) => h.id === id)?.name || id;
  }

  function vatCode(id) {
    return vats.find((v) => v.id === id)?.vatCode || id;
  }

  // 某合批行可选缸：同坊就绪缸（当前成员必在其中）
  function rowVats(row) {
    return vats.filter((v) => v.dyeHouseId === row.dyeHouseId && v.status === 'ready');
  }

  function toggleCreate(vatId) {
    const set = new Set(form.vatIds);
    if (set.has(vatId)) set.delete(vatId);
    else set.add(vatId);
    form.vatIds = [...set];
  }

  function toggleMember(batchId, vatId) {
    const cur = new Set(memberDraft[batchId] || []);
    if (cur.has(vatId)) cur.delete(vatId);
    else cur.add(vatId);
    memberDraft = { ...memberDraft, [batchId]: [...cur] };
  }

  async function save() {
    error = '';
    try {
      const body = {
        dyeHouseId: houseId,
        batchCode: form.batchCode.trim(),
        fabricLimitKg: Number(form.fabricLimitKg),
        vatIds: form.vatIds,
      };
      if (editing) {
        await api(`/combine-batches/${editing}`, {
          method: 'PUT',
          body: JSON.stringify({
            batchCode: body.batchCode,
            fabricLimitKg: body.fabricLimitKg,
          }),
        });
      } else {
        await api('/combine-batches', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      form = { dyeHouseId: form.dyeHouseId, batchCode: '', fabricLimitKg: 100, vatIds: [] };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    form = {
      dyeHouseId: String(row.dyeHouseId),
      batchCode: row.batchCode,
      fabricLimitKg: row.fabricLimitKg,
      vatIds: row.members.map((m) => m.vatId),
    };
  }

  async function saveMembers(row) {
    error = '';
    try {
      await api(`/combine-batches/${row.id}/members`, {
        method: 'PUT',
        body: JSON.stringify({ vatIds: memberDraft[row.id] || [] }),
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function lock(row) {
    error = '';
    try {
      await api(`/combine-batches/${row.id}/lock`, { method: 'POST' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function remove(row) {
    if (!confirm(`确认删除合批「${row.batchCode}」？`)) return;
    error = '';
    try {
      await api(`/combine-batches/${row.id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">拼缸合染</h1>
<p class="page-sub">
  一批挂多口同坊就绪缸；各缸最新染程布重之和不得超过布重上限。组批中可加减成员，满足至少两口缸且不超上限即可锁定，锁定后成员冻结。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >所属染坊
      <select bind:value={form.dyeHouseId} disabled={editing !== null}>
        {#each houses as h}
          <option value={String(h.id)}>{h.name}</option>
        {/each}
      </select>
    </label>
    <label>合批号 <input bind:value={form.batchCode} placeholder="同坊唯一" /></label>
    <label
      >布重上限 kg
      <input type="number" step="0.1" bind:value={form.fabricLimitKg} />
    </label>
  </div>

  {#if !editing}
    <div class="member-pick">
      <span class="pick-label">挂缸（仅就绪，可先空建后补）：</span>
      {#each selectableVats as v}
        <label class="chip">
          <input
            type="checkbox"
            checked={form.vatIds.includes(v.id)}
            on:change={() => toggleCreate(v.id)}
          />
          {v.vatCode} · {v.fiberType}
        </label>
      {/each}
      {#if selectableVats.length === 0}
        <span class="pick-empty">该染坊暂无就绪染缸</span>
      {/if}
    </div>
  {/if}

  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '新建合批'}</button>
    {#if editing}
      <button
        class="btn ghost"
        type="button"
        on:click={() => {
          editing = null;
          form = { ...form, batchCode: '', fabricLimitKg: 100, vatIds: [] };
        }}>取消</button
      >
    {/if}
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染坊</th>
        <th>合批号</th>
        <th>成员缸 / 最新布重</th>
        <th>合计 / 上限 kg</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{houseName(row.dyeHouseId)}</td>
          <td>{row.batchCode}</td>
          <td>
            {#if row.status === 'grouping'}
              <div class="member-pick tight">
                {#each rowVats(row) as v}
                  <label class="chip">
                    <input
                      type="checkbox"
                      checked={(memberDraft[row.id] || []).includes(v.id)}
                      on:change={() => toggleMember(row.id, v.id)}
                    />
                    {v.vatCode}
                  </label>
                {/each}
              </div>
            {:else}
              {row.members.map((m) => m.vatCode).join('、')}
            {/if}
          </td>
          <td>
            <span class:over={row.totalFabricKg > row.fabricLimitKg}>{row.totalFabricKg}</span>
            / {row.fabricLimitKg}
          </td>
          <td><span class="badge {row.status}">{COMBINE_STATUS[row.status] || row.status}</span></td>
          <td class="row-actions">
            {#if row.status === 'grouping'}
              <button class="btn ghost small" type="button" on:click={() => saveMembers(row)}>
                保存成员
              </button>
              <button class="btn small" type="button" on:click={() => lock(row)}>锁定</button>
              <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>
                编辑
              </button>
              <button class="btn danger small" type="button" on:click={() => remove(row)}>删除</button>
            {:else}
              <span class="locked-note">成员已冻结</span>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .member-pick {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.9rem;
    margin: 0.2rem 0 0.9rem;
  }

  .member-pick.tight {
    margin: 0;
  }

  .pick-label {
    color: var(--indigo-mist);
    font-size: 0.85rem;
  }

  .pick-empty {
    color: var(--warn);
    font-size: 0.85rem;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.85rem;
    border: 1px solid var(--line);
    border-radius: 2px;
    padding: 0.15rem 0.5rem;
  }

  .over {
    color: var(--warn);
    font-weight: 600;
  }

  .locked-note {
    color: var(--indigo-mist);
    font-size: 0.8rem;
  }

  .badge.grouping {
    color: #b8a8ff;
    border-color: rgba(107, 92, 231, 0.55);
    background: rgba(107, 92, 231, 0.15);
  }

  .badge.locked {
    color: var(--ok);
    border-color: rgba(76, 175, 130, 0.45);
  }
</style>
