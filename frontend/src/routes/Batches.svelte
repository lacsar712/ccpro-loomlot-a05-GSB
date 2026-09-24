<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, BATCH_STATUS } from '../lib/api.js';

  let houses = [];
  let vats = [];
  let lots = [];
  let rows = [];
  let error = '';
  let form = { dyeHouseId: '', batchNo: '', maxFabricKg: 100 };
  let editing = null;
  let memberBatchId = null;
  let memberVatId = '';

  async function load() {
    error = '';
    try {
      [houses, vats, lots, rows] = await Promise.all([
        api('/dye-houses'),
        api('/vats'),
        api('/dye-lots'),
        api('/combined-batches'),
      ]);
      if (!form.dyeHouseId && houses.length) form.dyeHouseId = String(houses[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function houseName(id) {
    return houses.find((h) => h.id === id)?.name || id;
  }

  function vatOf(id) {
    return vats.find((v) => v.id === id);
  }

  function vatCode(id) {
    return vatOf(id)?.vatCode || id;
  }

  // 各缸最新一条染程的布重（无染程计 0）
  function latestLotKg(vatId) {
    let best = null;
    for (const l of lots) {
      if (l.vatId !== vatId) continue;
      const t = new Date(l.startedAt).getTime();
      if (!best || t > best.t || (t === best.t && l.id > best.id)) {
        best = { t, id: l.id, fabricKg: l.fabricKg };
      }
    }
    return best ? best.fabricKg : 0;
  }

  function batchTotal(batch) {
    return batch.members.reduce((s, m) => s + latestLotKg(m.vatId), 0);
  }

  // 已被其他合批占用的缸（组批中/已锁定均占用）
  function occupiedVatIds(exceptBatchId) {
    const set = new Set();
    for (const b of rows) {
      if (b.id === exceptBatchId) continue;
      for (const m of b.members) set.add(m.vatId);
    }
    return set;
  }

  $: memberBatch = rows.find((r) => r.id === memberBatchId) || null;
  $: memberTotal = memberBatch ? batchTotal(memberBatch) : 0;
  $: candidateVats = memberBatch
    ? vats.filter(
        (v) =>
          v.dyeHouseId === memberBatch.dyeHouseId &&
          v.status === 'ready' &&
          !memberBatch.members.some((m) => m.vatId === v.id) &&
          !occupiedVatIds(memberBatch.id).has(v.id)
      )
    : [];
  $: if (memberBatch && !candidateVats.some((v) => String(v.id) === memberVatId)) {
    memberVatId = candidateVats.length ? String(candidateVats[0].id) : '';
  }

  async function save() {
    error = '';
    try {
      if (editing) {
        await api(`/combined-batches/${editing}`, {
          method: 'PUT',
          body: JSON.stringify({
            batchNo: form.batchNo.trim(),
            maxFabricKg: Number(form.maxFabricKg),
          }),
        });
      } else {
        await api('/combined-batches', {
          method: 'POST',
          body: JSON.stringify({
            dyeHouseId: Number(form.dyeHouseId),
            batchNo: form.batchNo.trim(),
            maxFabricKg: Number(form.maxFabricKg),
          }),
        });
      }
      editing = null;
      form = { dyeHouseId: form.dyeHouseId, batchNo: '', maxFabricKg: 100 };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    form = {
      dyeHouseId: String(row.dyeHouseId),
      batchNo: row.batchNo,
      maxFabricKg: row.maxFabricKg,
    };
  }

  async function remove(id) {
    if (!confirm('确认删除该合批？成员关系将一并解除。')) return;
    error = '';
    try {
      await api(`/combined-batches/${id}`, { method: 'DELETE' });
      if (memberBatchId === id) memberBatchId = null;
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function lock(id) {
    if (!confirm('确认锁定该合批？锁定后禁止改动成员。')) return;
    error = '';
    try {
      await api(`/combined-batches/${id}/lock`, { method: 'POST' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function openMembers(row) {
    memberBatchId = row.id;
    memberVatId = '';
  }

  async function addMember() {
    if (!memberVatId) return;
    error = '';
    try {
      await api(`/combined-batches/${memberBatchId}/members`, {
        method: 'POST',
        body: JSON.stringify({ vatId: Number(memberVatId) }),
      });
      memberVatId = '';
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function removeMember(vatId) {
    error = '';
    try {
      await api(`/combined-batches/${memberBatchId}/members/${vatId}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">拼缸合染</h1>
<p class="page-sub">
  同坊就绪染缸组批合染；一口缸同时只能进一个合批。锁定需至少两口缸，且各缸最新染程布重之和不超过布重上限。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >所属染坊
      <select bind:value={form.dyeHouseId} disabled={!!editing}>
        {#each houses as h}
          <option value={String(h.id)}>{h.name}</option>
        {/each}
      </select>
    </label>
    <label>合批号 <input bind:value={form.batchNo} placeholder="如 PB-002" /></label>
    <label
      >布重上限 (kg) <input type="number" step="0.1" min="0" bind:value={form.maxFabricKg} /></label
    >
  </div>
  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '新建合批'}</button>
    {#if editing}
      <button
        class="btn ghost"
        type="button"
        on:click={() => {
          editing = null;
          form = { dyeHouseId: form.dyeHouseId, batchNo: '', maxFabricKg: 100 };
        }}>取消</button
      >
    {/if}
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel" style="margin-bottom:1rem;">
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染坊</th>
        <th>合批号</th>
        <th>上限 kg</th>
        <th>成员缸</th>
        <th>最新染程合计</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{houseName(row.dyeHouseId)}</td>
          <td>{row.batchNo}</td>
          <td>{row.maxFabricKg}</td>
          <td>{row.members.length ? row.members.map((m) => vatCode(m.vatId)).join('、') : '—'}</td>
          <td class:over={batchTotal(row) > row.maxFabricKg}>
            {batchTotal(row).toFixed(1)} / {row.maxFabricKg} kg
          </td>
          <td><span class="badge {row.status}">{BATCH_STATUS[row.status] || row.status}</span></td>
          <td class="row-actions">
            <button class="btn ghost small" type="button" on:click={() => openMembers(row)}>
              {row.status === 'grouping' ? '成员' : '查看成员'}
            </button>
            {#if row.status === 'grouping'}
              <button class="btn small" type="button" on:click={() => lock(row.id)}>锁定</button>
              <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
              <button class="btn danger small" type="button" on:click={() => remove(row.id)}>删除</button>
            {/if}
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

{#if memberBatch}
  <div class="panel">
    <p style="margin:0 0 0.75rem;color:var(--indigo-mist);font-size:0.9rem;">
      成员管理 · <strong>{memberBatch.batchNo}</strong>（{BATCH_STATUS[memberBatch.status]}）·
      最新染程合计
      <strong class:over={memberTotal > memberBatch.maxFabricKg}>
        {memberTotal.toFixed(1)} kg</strong
      >
      / 上限 {memberBatch.maxFabricKg} kg · 锁定需 ≥2 口缸且不超上限
    </p>
    {#if memberBatch.status === 'grouping'}
      <div class="toolbar">
        <select bind:value={memberVatId}>
          {#each candidateVats as v}
            <option value={String(v.id)}>{v.vatCode} · {v.fiberType} · {v.capacityL}L</option>
          {/each}
        </select>
        <button class="btn small" type="button" disabled={!memberVatId} on:click={addMember}>
          加入成员
        </button>
        {#if !candidateVats.length}
          <span class="page-sub" style="margin:0;">本坊暂无可入批的就绪染缸。</span>
        {/if}
      </div>
    {/if}
    <table>
      <thead>
        <tr>
          <th>缸号</th>
          <th>纤维</th>
          <th>缸状态</th>
          <th>最新染程 kg</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {#each memberBatch.members as m}
          <tr>
            <td>{vatCode(m.vatId)}</td>
            <td>{vatOf(m.vatId)?.fiberType || '—'}</td>
            <td>
              <span class="badge {vatOf(m.vatId)?.status}">
                {VAT_STATUS[vatOf(m.vatId)?.status] || vatOf(m.vatId)?.status || '—'}
              </span>
            </td>
            <td>{latestLotKg(m.vatId)}</td>
            <td class="row-actions">
              {#if memberBatch.status === 'grouping'}
                <button class="btn danger small" type="button" on:click={() => removeMember(m.vatId)}>
                  移出
                </button>
              {/if}
            </td>
          </tr>
        {:else}
          <tr><td colspan="5" style="color:var(--indigo-mist);">暂无成员缸</td></tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
