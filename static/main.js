const chat = document.getElementById('chat');
const inputForm = document.getElementById('inputForm');
const userInput = document.getElementById('userInput');
const quick = document.getElementById('quickActions');

function addMessage(content, sender='bot') {
  const wrapper = document.createElement('div');
  wrapper.className = 'message ' + (sender==='user' ? 'user' : 'bot');
  const bubble = document.createElement('div');
  bubble.className = 'bubble ' + (sender==='user' ? 'user' : 'bot');
  if (typeof content === 'string') bubble.innerHTML = content;
  else bubble.appendChild(content); // element
  wrapper.appendChild(bubble);
  chat.appendChild(wrapper);
  chat.scrollTop = chat.scrollHeight;
}

function renderRecommendations(items){
  if(!items || items.length===0){
    addMessage("No results. Try a different genre or 'popular movies'.");
    return;
  }
  const container = document.createElement('div');
  items.forEach(it => {
    const card = document.createElement('div');
    card.className = 'reco-card';
    const img = document.createElement('img');
    img.className = 'reco-thumb';
    img.src = it.poster || '/static/no-poster.png';
    img.alt = it.title;

    const body = document.createElement('div');
    body.className = 'reco-body';
    body.innerHTML = `<div class="reco-title">${it.title}</div>
                      <div class="reco-meta small">${it.release_date || ''} • rating ${it.rating || 'N/A'}</div>
                      <div class="small">${it.overview || ''}</div>`;

    const actions = document.createElement('div');
    actions.className = 'card-actions';
    const dbtn = document.createElement('button'); dbtn.className='btn'; dbtn.textContent='Details';
    dbtn.onclick = () => fetch(`/api/movie/${it.id}`).then(r=>r.json()).then(d=>{
      if(d.movie) {
        addMessage(`<strong>${d.movie.title}</strong><br>${d.movie.overview || ''}<br><em>Release: ${d.movie.release_date || 'N/A'} — Rating: ${d.movie.rating || 'N/A'}</em>`);
      }
    });
    const mbtn = document.createElement('button'); mbtn.className='btn'; mbtn.textContent='More like this';
    mbtn.onclick = () => fetch(`/api/movie/${it.id}/similar`).then(r=>r.json()).then(d=>{
      if(d.results) {
        addMessage(`Movies similar to <strong>${it.title}</strong>:`);
        renderRecommendations(d.results);
      }
    });
    actions.appendChild(dbtn); actions.appendChild(mbtn);

    body.appendChild(actions);
    card.appendChild(img);
    card.appendChild(body);
    container.appendChild(card);
  });
  addMessage(container, 'bot');
}

async function sendMsg(text){
  addMessage(text, 'user');
  const res = await fetch('/api/message', {
    method:'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({text})
  });
  const j = await res.json();
  if(j.type === 'text'){
    addMessage(j.message);
  } else if(j.type === 'recommend'){
    addMessage("Here are some suggestions:");
    renderRecommendations(j.results);
  } else if(j.type === 'details'){
    const mv = j.movie;
    addMessage(`<strong>${mv.title}</strong><br>${mv.overview || ''}<br><em>Release: ${mv.release_date || 'N/A'} — Rating: ${mv.rating || 'N/A'}</em>`);
  } else if(j.type === 'error'){
    addMessage("Error: " + j.message);
  } else {
    addMessage("Sorry, couldn't understand the response.");
  }
}

inputForm.addEventListener('submit', e => {
  e.preventDefault();
  const txt = userInput.value.trim();
  if(!txt) return;
  userInput.value='';
  sendMsg(txt);
});

quick.addEventListener('click', e => {
  const t = e.target;
  if(t.dataset && t.dataset.text){
    sendMsg(t.dataset.text);
  }
});

// startup greeting
addMessage("Hi — I'm MovieBot. Ask me for recommendations, e.g. 'Recommend sci-fi movies' or 'Show popular movies'.");
