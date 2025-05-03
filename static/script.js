const socket = io();

// ===============================
// Cliente - Entrar na fila (Revisado)
// ===============================
function entrarFila() {
    const nomeInput = document.getElementById('nome');
    const telefoneInput = document.getElementById('telefone');
    const btnEntrar = document.getElementById('btn-entrar');
    const nome = nomeInput.value.trim();
    const telefone = telefoneInput.value.trim();

    clearFieldError(nomeInput);
    clearFieldError(telefoneInput);

    if (!nome) {
        setFieldError(nomeInput, 'Nome é obrigatório.');
        return;
    }

    if (!/^[\d]{10,15}$/.test(telefone)) {
        setFieldError(telefoneInput, 'Telefone inválido. Use apenas números (10-15 dígitos).');
        return;
    }

    btnEntrar.disabled = true;
    btnEntrar.textContent = 'Entrando...';

    fetch('/entrar-fila', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ telefone, nome })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) throw new Error(data.error);

        localStorage.setItem('cliente_id', data.cliente_id);
        localStorage.setItem('cliente_nome', data.nome);

        document.getElementById('login-section').style.display = 'none';
        document.getElementById('fila-section').style.display = 'block';
        document.getElementById('nome-cliente').textContent = data.nome;

        if (window.posicaoIntervalId) clearInterval(window.posicaoIntervalId);
        atualizarPosicao();
        window.posicaoIntervalId = setInterval(atualizarPosicao, 5000);

        showAlert(`🎉 Você entrou na fila, ${data.nome}!`, 'success');
    })
    .catch(error => {
        showAlert(`❌ ${error.message || 'Erro ao entrar na fila.'}`, 'error');
        console.error('Erro entrarFila:', error);
    })
    .finally(() => {
        btnEntrar.disabled = false;
        btnEntrar.textContent = 'Entrar na Fila';
    });
}

// ===============================
// Validação visual ao vivo
// ===============================
document.querySelectorAll('input').forEach(input => {
    input.addEventListener('input', () => {
        clearFieldError(input);
    });
});

function setFieldError(input, message) {
    input.classList.add('input-error');
    const label = input.nextElementSibling;
    if (label) label.setAttribute('data-error', message);
}

function clearFieldError(input) {
    input.classList.remove('input-error');
    const label = input.nextElementSibling;
    if (label) label.removeAttribute('data-error');
}

// ===============================
// Atualizar posição
// ===============================
function atualizarPosicao() {
    const clienteId = localStorage.getItem('cliente_id');
    if (!clienteId) {
        showAlert('Sessão expirada. Entre novamente na fila.', 'error');
        resetarInterfaceCliente();
        return;
    }

    fetch(`/posicao/${clienteId}`)
    .then(response => response.json())
    .then(data => {
        if (data.error) throw new Error(data.error);

        document.getElementById('posicao').textContent = data.posicao;
        document.getElementById('total').textContent = data.total;
        document.getElementById('frente').textContent = data.posicao - 1;

        const tempoEstimado = Math.max(5, (data.posicao - 1) * 5);
        document.getElementById('tempo-espera').textContent = tempoEstimado;
    })
    .catch(error => {
        if (error.message.includes('Não está na fila')) {
            resetarInterfaceCliente();
        }
        showAlert(`⚠️ ${error.message || 'Erro ao atualizar posição.'}`, 'error');
    });
}

function resetarInterfaceCliente() {
    localStorage.removeItem('cliente_id');
    localStorage.removeItem('cliente_nome');
    document.getElementById('login-section').style.display = 'block';
    document.getElementById('fila-section').style.display = 'none';
    if (window.posicaoIntervalId) clearInterval(window.posicaoIntervalId);
}

// ===============================
// Cliente - Responder ao chamado
// ===============================
socket.on('cliente_chamado', (data) => {
    const clienteId = localStorage.getItem('cliente_id');
    if (data.cliente_id === clienteId) {
        const notificacao = document.getElementById('notificacao');
        notificacao.innerHTML = '<strong>SUA VEZ!</strong> Dirija-se à barbearia.';
        notificacao.className = 'notificacao atencao ativo';

        try {
            const audio = new Audio('/static/assets/alerta.mp3');
            audio.play().catch(e => console.warn('Áudio não pôde ser reproduzido:', e));
        } catch (e) {
            console.error('Erro no áudio:', e);
        }

        if (window.posicaoIntervalId) clearInterval(window.posicaoIntervalId);
    }
});

// ===============================
// Cliente - Sair da fila
// ===============================
function sairFila() {
    const clienteId = localStorage.getItem('cliente_id');
    if (!clienteId) {
        showAlert('Você não está na fila.', 'warning');
        return;
    }

    if (!confirm('Tem certeza que deseja sair da fila?')) return;

    fetch(`/sair-fila/${clienteId}`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
    .then(response => response.json())
    .then(() => {
        showAlert('Você saiu da fila. Obrigado por usar nosso sistema! 🙌', 'success');
        resetarInterfaceCliente();
    })
    .catch(error => {
        showAlert(`❌ ${error.message || 'Erro ao sair da fila.'}`, 'error');
    });
}

// ===============================
// Admin - Carregar fila
// ===============================
if (document.getElementById('lista-fila')) {
    const adminSocket = io();

    function carregarFila() {
        fetch('/fila')
        .then(response => response.json())
        .then(data => {
            const lista = document.getElementById('lista-fila');
            const totalClientes = document.getElementById('total-clientes');

            lista.innerHTML = data.fila.length 
                ? data.fila.map((cliente, index) => `
                    <li class="cliente-item">
                        <span class="posicao">${index + 1}</span>
                        <span class="nome">${cliente.nome}</span>
                        <span class="telefone">${cliente.telefone}</span>
                        <span class="hora">${new Date(cliente.entrada).toLocaleTimeString()}</span>
                    </li>
                  `).join('')
                : '<li class="vazia">Nenhum cliente na fila</li>';

            totalClientes.textContent = data.fila.length;
        })
        .catch(error => {
            showAlert(`❌ ${error.message || 'Erro ao carregar fila.'}`, 'error');
            console.error('Erro carregarFila:', error);
        });
    }

    function chamarProximo() {
        fetch('/proximo', { 
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) throw new Error(data.error);

            const clienteAtual = document.getElementById('cliente-atual');
            clienteAtual.innerHTML = `
                <h3>Atendimento Atual</h3>
                <p>${data.nome} (${data.telefone})</p>
                <small>${new Date().toLocaleTimeString()}</small>
            `;

            showAlert(`✅ Chamando: ${data.nome}`, 'success');
            carregarFila();
        })
        .catch(error => {
            showAlert(`❌ ${error.message || 'Erro ao chamar próximo cliente.'}`, 'error');
        });
    }

    adminSocket.on('atualizar_fila', carregarFila);
    carregarFila();
    setInterval(carregarFila, 10000);
}

// ===============================
// Alertas visuais - Melhorados
// ===============================
function showAlert(message, type = 'info', duration = 4000) {
    const alertDiv = document.getElementById('alert');
    if (!alertDiv) return;

    alertDiv.innerHTML = message;
    alertDiv.className = '';
    alertDiv.classList.add('alert', `alert-${type}`);
    alertDiv.style.display = 'block';
    alertDiv.style.opacity = '1';

    setTimeout(() => {
        alertDiv.style.opacity = '0';
        setTimeout(() => {
            alertDiv.style.display = 'none';
        }, 500);
    }, duration);
}
