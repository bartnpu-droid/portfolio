<?php
/**
 * Free shipping progress block: first render on the server, updated in the browser by view.js.
 *
 * @package Ombra\StoreTools
 *
 * @var array $attributes Block attributes.
 */

use Ombra\StoreTools\Free_Shipping;

defined( 'ABSPATH' ) || exit;

if ( ! function_exists( 'WC' ) ) {
	return;
}

$ombra_data = Free_Shipping::data();
if ( ! $ombra_data['enabled'] ) {
	return;
}

$ombra_variant = ( $attributes['variant'] ?? 'bar' ) === 'text' ? 'text' : 'bar';
$ombra_percent = (int) round( $ombra_data['progress'] * 100 );
$ombra_classes = array( 'ombra-fsb', 'ombra-fsb--' . $ombra_variant );
if ( $ombra_data['unlocked'] ) {
	$ombra_classes[] = 'is-unlocked';
}
if ( $ombra_data['is_empty'] ) {
	$ombra_classes[] = 'is-empty';
}

$ombra_wrapper = get_block_wrapper_attributes(
	array(
		'class'                => implode( ' ', $ombra_classes ),
		'data-ombra-fsb'       => $ombra_variant,
		'data-ombra-fsb-cart'  => esc_url_raw( rest_url( 'wc/store/v1/cart' ) ),
		'style'                => '--ombra-fsb-color:' . $ombra_data['color'],
	)
);
?>
<div <?php echo $ombra_wrapper; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped -- escaped by get_block_wrapper_attributes(). ?>>
	<p class="ombra-fsb__message" aria-live="polite"><?php echo esc_html( $ombra_data['message'] ); ?></p>
	<?php if ( 'bar' === $ombra_variant ) : ?>
		<div class="ombra-fsb__track" role="progressbar" aria-label="<?php echo esc_attr( $ombra_data['message'] ); ?>" aria-valuemin="0" aria-valuemax="100" aria-valuenow="<?php echo esc_attr( (string) $ombra_percent ); ?>">
			<span class="ombra-fsb__fill" style="width:<?php echo esc_attr( (string) $ombra_percent ); ?>%"></span>
		</div>
	<?php endif; ?>
</div>
