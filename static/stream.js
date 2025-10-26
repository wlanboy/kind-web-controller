let currentStream = null;

function startStream(task, name) {
  if (currentStream) currentStream.close();
  const output = document.querySelector('#live-output code');
  output.textContent = "";
  const url = `/stream?task=${task}&name=${name}`;
  currentStream = new EventSource(url);

  currentStream.onmessage = (event) => {
    if (event.data === "[STREAM CLOSED]") {
      console.log("[DEBUG] Stream finished cleanly.");
      currentStream.close();

      if (["create", "delete"].includes(task)) {
        htmx.ajax('GET', '/configs', { target: '#configs', swap: 'innerHTML' });
        htmx.ajax('GET', '/clusters', { target: '#active-clusters', swap: 'innerHTML' });
      }
      return;
    }
    output.textContent += event.data + "\n";
  };

  currentStream.onerror = (err) => {
    console.warn("[SSE ERROR]", err);
    currentStream.close();
  };
}

function startStreamMetallb(name) {
  if (currentStream) currentStream.close();
  const output = document.querySelector('#live-output code');
  output.textContent = "";
  const url = `/streammetallb?name=${name}`;
  currentStream = new EventSource(url);

  currentStream.onmessage = (event) => {
    if (event.data === "[STREAM CLOSED]") {
      console.log("[DEBUG] MetalLB stream finished.");
      currentStream.close();
      htmx.ajax('GET', '/configs', { target: '#configs', swap: 'innerHTML' });
      htmx.ajax('GET', '/clusters', { target: '#active-clusters', swap: 'innerHTML' });
      return;
    }
    output.textContent += event.data + "\n";
  };

  currentStream.onerror = (err) => {
    console.warn("[SSE ERROR]", err);
    currentStream.close();
  };
}
