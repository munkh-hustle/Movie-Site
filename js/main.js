document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    // Display newest BL movies
    const blMoviesContainer = document.getElementById('bl-movies');
    const blMovies = getMoviesByCategory('bl')
        .sort((a, b) => new Date(b.release) - new Date(a.release))
        .slice(0, 5);
    
    blMoviesContainer.innerHTML = blMovies.map(createMovieCard).join('');
    
    // Display newest GL movies
    const glMoviesContainer = document.getElementById('gl-movies');
    const glMovies = getMoviesByCategory('gl')
        .sort((a, b) => new Date(b.release) - new Date(a.release))
        .slice(0, 5);
    
    glMoviesContainer.innerHTML = glMovies.map(createMovieCard).join('');
});