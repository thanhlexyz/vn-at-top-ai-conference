(function () {
	var STEP_X = 160, STEP_Y = 80;

	function wideTable() {
		var best = null, bestDistance = Infinity, middle = window.innerHeight / 2;
		document.querySelectorAll(".scroll").forEach(function (box) {
			if (box.scrollWidth <= box.clientWidth) return;
			var r = box.getBoundingClientRect();
			if (r.bottom < 0 || r.top > window.innerHeight) return;
			var d = middle < r.top ? r.top - middle : middle > r.bottom ? middle - r.bottom : 0;
			if (d < bestDistance) { best = box; bestDistance = d; }
		});
		return best;
	}

	document.addEventListener("keydown", function (e) {
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		var t = e.target;
		if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
		var dx = 0, dy = 0;
		switch (e.key) {
			case "h": case "ArrowLeft": dx = -STEP_X; break;
			case "l": case "ArrowRight": dx = STEP_X; break;
			case "j": dy = STEP_Y; break;
			case "k": dy = -STEP_Y; break;
			default: return;
		}
		if (dx) {
			var box = wideTable();
			if (!box) return;
			box.scrollBy({ left: dx, behavior: "smooth" });
		} else {
			window.scrollBy({ top: dy, behavior: "smooth" });
		}
		e.preventDefault();
	});
})();

(function () {

	function number(text) {
		var t = text.replace(/,/g, "");
		var m = t.match(/-?\d+(\.\d+)?/);
		if (!m) return null;
		var extra = t.slice(m.index + m[0].length).match(/\+\s*(\d+)/);
		var official = parseFloat(m[0]);
		return extra ? official + parseInt(extra[1], 10) + official / 1000 : official + official / 1000;
	}

	function leafHeadings(thead) {
		var grid = [], leaves = [];
		Array.prototype.forEach.call(thead.rows, function (row, r) {
			grid[r] = grid[r] || [];
			var c = 0;
			Array.prototype.forEach.call(row.cells, function (cell) {
				while (grid[r][c]) c++;
				var rs = cell.rowSpan || 1, cs = cell.colSpan || 1;
				for (var i = 0; i < rs; i++) for (var j = 0; j < cs; j++) {
					grid[r + i] = grid[r + i] || [];
					grid[r + i][c + j] = cell;
				}
				if (cs === 1 && r + rs === thead.rows.length) leaves.push([cell, c]);
				c += cs;
			});
		});
		return leaves;
	}

	function hiddenRow(table, tr) {
		return table.classList.contains("rows-collapsed") && tr.classList.contains("more-row");
	}
	function renumber(table) {
		var k = 0;
		Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
			var n = tr.querySelector("td.rank .n");
			if (!n || tr.classList.contains("total") || hiddenRow(table, tr)) return;
			n.textContent = ++k;
		});
	}

	function sortBy(table, column, cell) {
		var body = table.tBodies[0];
		var rows = Array.prototype.filter.call(body.rows, function (tr) { return !tr.classList.contains("total"); });
		var totals = Array.prototype.filter.call(body.rows, function (tr) { return tr.classList.contains("total"); });
		var values = rows.map(function (tr) {
			var td = tr.cells[column], text = td ? td.textContent.trim() : "";

			if (td && td.hasAttribute("data-last")) text = "";
			return { tr: tr, text: text, num: number(text) };
		});
		var numeric = values.filter(function (v) { return v.text && v.text !== "–"; }).every(function (v) { return v.num !== null; });
		var previous = cell.getAttribute("aria-sort");
		var order = previous ? (previous === "descending" ? "ascending" : "descending") : (numeric ? "descending" : "ascending");
		var sign = order === "ascending" ? 1 : -1;
		values.sort(function (a, b) {
			var ea = !a.text || a.text === "–", eb = !b.text || b.text === "–";
			if (ea !== eb) return ea ? 1 : -1;
			if (numeric) return sign * ((a.num || 0) - (b.num || 0));
			return sign * a.text.localeCompare(b.text);
		});
		table.querySelectorAll("th[aria-sort]").forEach(function (th) { th.removeAttribute("aria-sort"); });
		cell.setAttribute("aria-sort", order);
		values.forEach(function (v) { body.appendChild(v.tr); });
		totals.forEach(function (tr) { body.appendChild(tr); });
		renumber(table);
		podium(table, numeric && !cell.hasAttribute("data-nocup") ? column : null, order === "ascending");
		if (table.paginate) table.paginate(0, false);
	}

	var CUP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10v2h3v3a4 4 0 0 1-4 4h-.3A5 5 0 0 1 13 14.9V18h3v2H8v-2h3v-3.1A5 5 0 0 1 8.3 12H8a4 4 0 0 1-4-4V5h3V3zm0 4H6v1a2 2 0 0 0 1 1.7V7zm10 0v2.7A2 2 0 0 0 18 8V7h-1z"/></svg>';
	var PLACES = ["gold", "silver", "bronze"];
	function podium(table, column, ascending) {
		if (!table.classList.contains("podium")) return;
		table.lastPodium = [column, ascending];
		var rows = Array.prototype.filter.call(table.tBodies[0].rows, function (tr) { return !tr.classList.contains("total"); });
		var place = -1, last = null, k = -1;
		rows.forEach(function (tr) {
			var slot = tr.querySelector(".cup");
			if (!slot) return;
			if (hiddenRow(table, tr)) { slot.className = "cup"; slot.innerHTML = ""; slot.removeAttribute("title"); return; }
			k += 1;
			var cell = column === undefined || column === null ? null : tr.cells[column];
			var key = column === undefined ? k : !cell || cell.hasAttribute("data-last") ? null : number(cell.textContent);

			var nothing = column !== undefined && key === 0 && !ascending;
			if (key === null && column !== undefined) { place = 99; }
			else if (!nothing && (place < 0 || key !== last)) { place += 1; }
			if (!nothing) last = key;
			slot.className = "cup";
			slot.innerHTML = "";
			slot.removeAttribute("title");
			if (place >= 0 && place < 3 && !nothing) {
				slot.classList.add(PLACES[place]);
				slot.innerHTML = CUP;
				slot.title = "#" + (place + 1);
			}
		});
	}

	document.querySelectorAll("table.podium").forEach(function (table) {
		var start = leafHeadings(table.tHead).filter(function (pair) { return pair[0].hasAttribute("data-podium"); })[0];
		podium(table, start ? start[1] : undefined);
	});

	document.querySelectorAll("table[data-collapsible]").forEach(function (table) {
		var columns = leafHeadings(table.tHead).filter(function (pair) { return pair[0].hasAttribute("data-extra"); })
			.map(function (pair) { return pair[1]; });
		Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
			columns.forEach(function (c) { if (tr.cells[c]) tr.cells[c].classList.add("xcol"); });
		});
		var button = (table.id && document.querySelector('button.more-columns[aria-controls="' + table.id + '"]'))
			|| document.querySelector("button.more-columns");
		if (!button) return;

		var show = (columns.length === 1 && button.dataset.showOne ? button.dataset.showOne : button.dataset.show)
			.replace("{n}", columns.length);

		var names = Array.prototype.map.call(table.tHead.rows[0].querySelectorAll("th[data-extra]"), function (th) {
			return th.textContent.replace(/\s+/g, " ").trim();
		}).filter(function (n) { return n; });
		button.textContent = show;
		if (names.length) button.title = button.dataset.names.replace("{names}", names.join(", "));
		button.addEventListener("click", function () {
			var hidden = table.classList.toggle("collapsed");
			button.textContent = hidden ? show : button.dataset.hide;
			button.setAttribute("aria-expanded", hidden ? "false" : "true");
			window.dispatchEvent(new Event("resize"));
		});
	});

	document.querySelectorAll("table[data-rows-collapsible]").forEach(function (table) {
		var button = table.id && document.querySelector('button.more-rows[aria-controls="' + table.id + '"]');
		if (!button) return;
		button.hidden = false;
		button.addEventListener("click", function () {
			var hidden = table.classList.toggle("rows-collapsed");
			button.textContent = hidden ? button.dataset.show : button.dataset.hide;
			button.setAttribute("aria-expanded", hidden ? "false" : "true");
			renumber(table);
			if (table.lastPodium) podium(table, table.lastPodium[0], table.lastPodium[1]);
			window.dispatchEvent(new Event("resize"));
		});
	});

	document.querySelectorAll("table[data-page-size]").forEach(function (table) {
		var size = parseInt(table.dataset.pageSize, 10), body = table.tBodies[0];
		var nav = table.id && document.querySelector('nav.pager[aria-controls="' + table.id + '"]');
		if (!size || !nav) return;
		function rows() { return Array.prototype.filter.call(body.rows, function (tr) { return !tr.classList.contains("total"); }); }
		function link(label, page, current, disabled) {
			var b = document.createElement("button");
			b.type = "button";
			b.textContent = label;
			if (current) b.setAttribute("aria-current", "page");
			if (disabled) b.disabled = true;
			b.addEventListener("click", function () { show(page, true); });
			return b;
		}
		function show(page, scroll) {
			var all = rows(), pages = Math.max(1, Math.ceil(all.length / size));
			page = Math.max(0, Math.min(page, pages - 1));
			all.forEach(function (tr, k) { tr.classList.toggle("off-page", Math.floor(k / size) !== page); });
			nav.innerHTML = "";
			nav.hidden = pages < 2;
			nav.appendChild(link(nav.dataset.prev, page - 1, false, page === 0));
			for (var p = 0; p < pages; p++) nav.appendChild(link(String(p + 1), p, p === page, false));
			nav.appendChild(link(nav.dataset.next, page + 1, false, page === pages - 1));
			if (scroll) table.scrollIntoView({ block: "start" });
			window.dispatchEvent(new Event("resize"));
		}
		table.paginate = show;
		show(0, false);
	});

	document.querySelectorAll("table").forEach(function (table) {
		if (!table.tHead || !table.tBodies[0] || table.tBodies[0].rows.length < 3) return;
		leafHeadings(table.tHead).forEach(function (pair) {
			var cell = pair[0], column = pair[1];
			if (cell.hasAttribute("data-nosort")) return;
			cell.classList.add("sortable");
			cell.tabIndex = 0;
			cell.title = (cell.title ? cell.title + ". " : "") + "Click to sort";
			cell.addEventListener("click", function () { sortBy(table, column, cell); });
			cell.addEventListener("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sortBy(table, column, cell); }
			});
		});
	});
})();

(function () {
	var links = Array.prototype.slice.call(document.querySelectorAll('.toc nav a[href^="#"]'));
	var items = links.map(function (a) { return { a: a, h: document.getElementById(decodeURIComponent(a.hash.slice(1))) }; })
		.filter(function (i) { return i.h; });
	if (!items.length) return;
	function mark() {
		var line = 100, current = items[0];
		items.forEach(function (i) { if (i.h.getBoundingClientRect().top <= line) current = i; });
		if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) current = items[items.length - 1];
		items.forEach(function (i) {
			var on = i === current;
			i.a.classList.toggle("current", on);
			if (on) i.a.setAttribute("aria-current", "location"); else i.a.removeAttribute("aria-current");
		});
	}
	window.addEventListener("scroll", mark, { passive: true });
	window.addEventListener("resize", mark);
	mark();
})();

(function () {
	var button = document.querySelector("nav .theme");
	if (!button) return;
	var root = document.documentElement;
	var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
	function current() { return root.dataset.theme || (media && media.matches ? "dark" : "light"); }
	function show() { button.textContent = current() === "dark" ? "☀️" : "🌙"; }
	button.addEventListener("click", function () {
		var next = current() === "dark" ? "light" : "dark";
		root.dataset.theme = next;
		try { localStorage.setItem("theme", next); } catch (e) {}
		show();
	});
	if (media && media.addEventListener) media.addEventListener("change", show);
	show();
})();

(function () {
	var legend = document.querySelector(".legend-box");
	document.querySelectorAll("svg.net").forEach(function (svg) {
		var pinned = null;
		function restore() { if (pinned) focus(pinned); else clear(); }
		svg.pin = function (id) { pinned = id; restore(); };
		function clear() {
			svg.classList.remove("focus");
			svg.querySelectorAll(".hl").forEach(function (el) { el.classList.remove("hl"); });
			if (legend) {
				legend.classList.remove("focus");
				legend.querySelectorAll(".hl").forEach(function (el) { el.classList.remove("hl"); });
			}
		}

		function lightLegend() {
			if (!legend) return;
			legend.classList.add("focus");
			svg.querySelectorAll(".node.hl").forEach(function (n) {
				legend.querySelectorAll("li[data-color]").forEach(function (li) {
					if (li.dataset.color === n.dataset.color) li.classList.add("hl");
				});
			});
		}
		function focus(id) {
			clear();
			svg.classList.add("focus");
			svg.querySelectorAll('.node[data-id="' + id + '"]').forEach(function (n) { n.classList.add("hl"); });
			svg.querySelectorAll(".edge, .ew").forEach(function (e) {
				var other = e.dataset.a === id ? e.dataset.b : e.dataset.b === id ? e.dataset.a : null;
				if (other === null) return;
				e.classList.add("hl");
				svg.querySelectorAll('.node[data-id="' + other + '"]').forEach(function (n) { n.classList.add("hl"); });
			});
			lightLegend();
		}
		function focusGroup(color) {
			clear();
			svg.classList.add("focus");
			var ids = {};
			svg.querySelectorAll(".node").forEach(function (n) {
				if (n.dataset.color === color) { ids[n.dataset.id] = true; n.classList.add("hl"); }
			});
			svg.querySelectorAll(".edge, .ew").forEach(function (e) {
				var other = ids[e.dataset.a] ? e.dataset.b : ids[e.dataset.b] ? e.dataset.a : null;
				if (other === null) return;
				e.classList.add("hl");
				svg.querySelectorAll('.node[data-id="' + other + '"]').forEach(function (n) { n.classList.add("hl"); });
			});
			lightLegend();
		}
		svg.querySelectorAll(".node").forEach(function (n) {
			n.addEventListener("mouseenter", function () { focus(n.dataset.id); });
			n.addEventListener("focus", function () { focus(n.dataset.id); });
			n.addEventListener("mouseleave", restore);
			n.addEventListener("blur", restore);
		});
		if (legend) {
			legend.querySelectorAll("li[data-color]").forEach(function (li) {
				li.addEventListener("mouseenter", function () { focusGroup(li.dataset.color); });
				li.addEventListener("focusin", function () { focusGroup(li.dataset.color); });
				li.addEventListener("mouseleave", restore);
				li.addEventListener("focusout", restore);
			});
		}
	});
})();

(function () {
	function measure() {
		document.querySelectorAll(".scroll.pinned").forEach(function (box) {
			box.classList.add("measured");
			var first = box.querySelector("td.pin0, th.pin0");
			box.style.setProperty("--pin0w", (first ? first.getBoundingClientRect().width : 0) + "px");
			var cell = box.querySelector("td.pin1, th.pin1");
			if (cell) box.style.setProperty("--pin1w", cell.getBoundingClientRect().width + "px");
		});
	}
	measure();
	window.addEventListener("resize", measure);
	if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
})();

(function () {
	var button = document.querySelector("form.feedback .fb-mail");
	if (!button) return;
	button.addEventListener("click", function () {
		var form = button.form;
		if (!form.reportValidity()) return;
		location.href = "mailto:" + button.dataset.to + "?subject=" + encodeURIComponent(form.elements.title.value) +
			"&body=" + encodeURIComponent(form.elements.body.value + "\n\n" + location.href);
	});
})();

(function () {
	var strip = document.querySelector("nav .links"), current = strip && strip.querySelector("a.current");
	if (strip && current && strip.scrollWidth > strip.clientWidth) {
		strip.scrollLeft = Math.max(0, current.offsetLeft - strip.offsetLeft - 16);
	}
})();

(function () {
	document.querySelectorAll("svg.net").forEach(function (svg) {
		var base = svg.viewBox.baseVal, X0 = base.x, Y0 = base.y, W = base.width, H = base.height;
		var v = { x: X0, y: Y0, w: W, h: H }, MAX = 6;
		function zoomed() { return v.w < W - 0.5; }
		function apply() {
			svg.setAttribute("viewBox", v.x + " " + v.y + " " + v.w + " " + v.h);
			svg.classList.toggle("zoomed", zoomed());
		}
		function clamp() {
			v.w = Math.min(W, Math.max(W / MAX, v.w));
			v.h = v.w * H / W;
			v.x = Math.min(X0 + W - v.w, Math.max(X0, v.x));
			v.y = Math.min(Y0 + H - v.h, Math.max(Y0, v.y));
		}
		function toSvg(cx, cy) {
			var p = svg.createSVGPoint();
			p.x = cx; p.y = cy;
			return p.matrixTransform(svg.getScreenCTM().inverse());
		}
		function zoom(factor, cx, cy) {
			var c = cx === undefined ? { x: v.x + v.w / 2, y: v.y + v.h / 2 } : toSvg(cx, cy);
			var w = Math.min(W, Math.max(W / MAX, v.w / factor)), k = w / v.w;
			v.x = c.x - (c.x - v.x) * k;
			v.y = c.y - (c.y - v.y) * k;
			v.w = w;
			clamp();
			apply();
		}
		function reset() { v = { x: X0, y: Y0, w: W, h: H }; apply(); }
		svg.zoomReset = reset;

		svg.addEventListener("wheel", function (e) {
			if (!(e.ctrlKey || e.metaKey)) return;
			e.preventDefault();
			zoom(Math.exp(-e.deltaY * 0.0025), e.clientX, e.clientY);
		}, { passive: false });

		var start = null, moved = false;
		svg.addEventListener("pointerdown", function (e) {
			if (e.button !== 0) return;
			start = { x: e.clientX, y: e.clientY, vx: v.x, vy: v.y, id: e.pointerId };
			moved = false;
		});
		svg.addEventListener("pointermove", function (e) {
			if (!start) return;
			var dx = e.clientX - start.x, dy = e.clientY - start.y;
			if (!moved) {
				if (!zoomed() || Math.sqrt(dx * dx + dy * dy) < 4) return;
				moved = true;
				svg.setPointerCapture(start.id);
				svg.classList.add("panning");
			}
			var s = v.w / svg.getBoundingClientRect().width;
			v.x = start.vx - dx * s;
			v.y = start.vy - dy * s;
			clamp();
			apply();
		});
		function end() {
			if (start && moved && svg.hasPointerCapture(start.id)) svg.releasePointerCapture(start.id);
			start = null;
			svg.classList.remove("panning");
		}
		svg.addEventListener("pointerup", end);
		svg.addEventListener("pointercancel", end);
		svg.addEventListener("click", function (e) {
			if (moved) { e.preventDefault(); e.stopPropagation(); moved = false; }
		}, true);
		svg.addEventListener("dragstart", function (e) { e.preventDefault(); });

		var tools = document.querySelector(".zoom-tools");
		if (!tools) return;
		tools.hidden = false;
		tools.querySelector("[data-zoom=in]").addEventListener("click", function () { zoom(1.5); });
		tools.querySelector("[data-zoom=out]").addEventListener("click", function () { zoom(1 / 1.5); });
		tools.querySelector("[data-zoom=reset]").addEventListener("click", reset);
	});
})();

(function () {
	var input = document.querySelector(".graph-search input"), svg = document.querySelector("svg.net");
	if (!input || !svg || !svg.pin) return;
	var box = input.closest(".graph-search"), status = box.querySelector(".search-status");
	box.hidden = false;
	function fold(t) {
		return t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\u0111/g, "d").replace(/\u0110/g, "D").toLowerCase().trim();
	}
	var nodes = Array.prototype.map.call(svg.querySelectorAll(".node"), function (n) {
		return { el: n, keys: [fold(n.dataset.name || ""), fold(n.dataset.alt || "")].filter(Boolean) };
	});
	function words(t) { return t.split(/[^a-z0-9]+/).filter(Boolean); }
	function find(q) {
		var k = fold(q), want = words(k);
		if (!k) return null;
		function first(test) { return nodes.filter(function (n) { return n.keys.some(test); })[0]; }
		function all(match) {
			return function (x) { var have = words(x); return want.every(function (w) { return have.some(function (h) { return match(h, w); }); }); };
		}
		return first(function (x) { return x === k; })
			|| first(all(function (h, w) { return h === w; }))
			|| first(all(function (h, w) { return h.indexOf(w) === 0; }))
			|| first(function (x) { return x.indexOf(k) >= 0; }) || null;
	}
	function go() {
		var q = input.value;
		if (!fold(q)) { svg.pin(null); status.textContent = ""; return; }
		var hit = find(q);
		if (!hit) { svg.pin(null); status.textContent = (input.dataset.none || "").replace("{q}", q); return; }
		if (svg.zoomReset) svg.zoomReset();
		svg.pin(hit.el.dataset.id);
		status.textContent = hit.el.dataset.name;
		var r = hit.el.querySelector("circle").getBoundingClientRect(), fig = svg.closest("figure");
		window.scrollTo({ top: window.scrollY + r.top + r.height / 2 - window.innerHeight / 2, behavior: "smooth" });
		if (fig && fig.scrollWidth > fig.clientWidth) fig.scrollLeft += r.left + r.width / 2 - window.innerWidth / 2;
	}
	input.addEventListener("change", go);
	input.addEventListener("keydown", function (e) { if (e.key === "Enter") { e.preventDefault(); go(); } });
	input.addEventListener("input", function () { if (!input.value) go(); });
})();
