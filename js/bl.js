document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    const moviesContainer = document.getElementById('movies-container');
    const pagination = document.getElementById('pagination');
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    
    let currentPage = 1;
    const moviesPerPage = 15;
    let filteredMovies = getMoviesByCategory('bl');
    
    function displayMovies(movies, page) {
        const start = (page - 1) * moviesPerPage;
        const end = start + moviesPerPage;
        const paginatedMovies = movies.slice(start, end);
        
        moviesContainer.innerHTML = paginatedMovies.map(createMovieCard).join('');
        
        // Update pagination
        const totalPages = Math.ceil(movies.length / moviesPerPage);
        pagination.innerHTML = '';
        
        for (let i = 1; i <= totalPages; i++) {
            const btn = document.createElement('button');
            btn.textContent = i;
            if (i === page) btn.classList.add('active');
            btn.addEventListener('click', () => {
                currentPage = i;
                displayMovies(filteredMovies, currentPage);
            });
            pagination.appendChild(btn);
        }
    }
    
    // Initial display
    displayMovies(filteredMovies, currentPage);
    
    // Search functionality
    function handleSearch() {
        const searchTerm = searchInput.value.toLowerCase();
        if (searchTerm) {
            filteredMovies = getMoviesByCategory('bl').filter(movie => 
                movie.title.toLowerCase().includes(searchTerm) ||
                movie.description.toLowerCase().includes(searchTerm)
            );
        } else {
            filteredMovies = getMoviesByCategory('bl');
        }
        currentPage = 1;
        displayMovies(filteredMovies, currentPage);
    }
    
    searchBtn.addEventListener('click', handleSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSearch();
    });
});