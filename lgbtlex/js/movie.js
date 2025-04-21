document.addEventListener('DOMContentLoaded', async () => {
    await loadMovieData();
    
    const movieTitle = getUrlParameter('title');
    if (!movieTitle || !movieData[movieTitle]) {
        window.location.href = 'lgbtlex.html';
        return;
    }
    
    const movie = movieData[movieTitle];
    
    // Set movie details - using title_name for display
    document.getElementById('movie-title').textContent = movie.title_name || movie.title;
    document.getElementById('movie-poster').src = movie.poster;
    document.getElementById('movie-poster').alt = movie.title_name || movie.title;
    document.getElementById('movie-year').textContent = movie.year;
    document.getElementById('movie-duration').textContent = movie.duration;
    document.getElementById('movie-rating').textContent = `${movie.rating} ★`;
    document.getElementById('movie-description').textContent = movie.description;
    document.getElementById('movie-cast').textContent = movie.cast;
    document.getElementById('movie-director').textContent = movie.director;
    document.getElementById('movie-release').textContent = movie.release;
    
    // Set genres
    const genresContainer = document.getElementById('movie-genres');
    genresContainer.innerHTML = movie.genre.split(', ').map(genre => 
        `<span>${genre}</span>`
    ).join('');
    
    // Set Telegram link (still using title for the backend)
    const telegramLink = document.getElementById('telegram-link');
    telegramLink.href = `https://t.me/meme_kino_bot?start=video_${encodeURIComponent(movie.title)}`;

    // Trailer
    const trailerLink = document.getElementById('trailer-link');
    trailerLink.href = `https://t.me/meme_kino_bot?start=trailer_${encodeURIComponent(movie.title)}`;
});